#!/usr/bin/env python3
"""Local HTTP regression tests for the opt-in U2NetP sidecar.

Uses in-memory synthetic PNGs and a mocked inference subprocess only.
No ONNX model, user image, remote network, or background services required.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import http.client
import importlib.util
import io
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
import zlib
from unittest.mock import patch

from PIL import Image

SOURCE = Path(__file__).with_name("loopback_u2netp_server.py")
spec = importlib.util.spec_from_file_location("photocraft_u2netp_http", SOURCE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

TOKEN = "temporary_test_token_with_at_least_32_characters"


def incomplete_authorization_headers() -> bytes:
    """Real CRLF-delimited HTTP headers with an unfinished bearer-token line.

    A literal backslash-r/backslash-n sequence never reaches the HTTP header
    parser and makes timeout tests pass without exercising authentication.
    """
    prefix = (
        b"POST /v1/remove-background HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\nAuthorization: Bearer "
    )
    assert b"\r\nAuthorization: Bearer " in prefix
    assert b"\\r\\n" not in prefix
    return prefix


def sample_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (20, 80, 160, 255)).save(buf, format="PNG")
    return buf.getvalue()


def crc_valid_but_undecodable_png() -> bytes:
    """Corrupt IDAT zlib data but recompute CRC: Pillow verify() still passes."""
    data = sample_png()
    chunk = data.index(b"IDAT") - 4
    length = int.from_bytes(data[chunk:chunk + 4], "big")
    start = chunk + 8
    end = start + length
    assert length >= 3
    invalid_zlib = b"\x78\x9c" + b"\xff" * (length - 2)
    checksum = zlib.crc32(b"IDAT" + invalid_zlib).to_bytes(4, "big")
    return data[:start] + invalid_zlib + checksum + data[end + 4:]


def oversized_ihdr_png() -> bytes:
    """CRC-correct PNG whose 400 MP header trips Pillow's early bomb guard."""
    data = sample_png()
    marker = data.index(b"IHDR")
    dimensions = marker + 4
    data = data[:dimensions] + (20_000).to_bytes(4, "big") * 2 + data[dimensions + 8:]
    crc_at = marker + 4 + 13
    return data[:crc_at] + zlib.crc32(data[marker:crc_at]).to_bytes(4, "big") + data[crc_at + 4:]


def mock_inference(argv, **_kwargs):
    source = Path(argv[argv.index("--input") + 1])
    dest = Path(argv[argv.index("--output") + 1])
    with Image.open(source) as img:
        size = img.size
    output = Image.new("RGBA", size, (80, 120, 200, 0))
    output.putpixel((8, 8), (80, 120, 200, 255))
    output.save(dest, format="PNG")
    return subprocess.CompletedProcess(argv, 0)


class LoopbackHTTPTests(unittest.TestCase):
    def setUp(self):
        self.httpd = server.LoopbackHTTPServer(("127.0.0.1", 0), server.make_handler(TOKEN))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.address = self.httpd.server_address

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def request(self, *, payload=None, token=TOKEN, consent="yes", mime="image/png", path="/v1/remove-background"):
        if payload is None:
            payload = sample_png()
        conn = http.client.HTTPConnection(*self.address, timeout=5)
        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": mime,
        }
        if consent is not None:
            headers["X-PhotoCraft-Image-Consent"] = consent
        try:
            conn.request("POST", path, body=payload, headers=headers)
            reply = conn.getresponse()
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            conn.close()

    def raw_request(self, raw: bytes) -> bytes:
        with socket.create_connection(self.address, timeout=3) as sock:
            sock.settimeout(3)
            sock.sendall(raw)
            buf = bytearray()
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
            return bytes(buf)

    def test_valid_consent_yields_bounded_alpha_png_with_no_persistent_files(self):
        with patch.object(server.subprocess, "run", side_effect=mock_inference) as run:
            code, headers, payload = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertLessEqual(len(payload), server.MAX_RESULT)
        with Image.open(io.BytesIO(payload)) as image:
            self.assertEqual(image.size, (16, 16))
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
            image.load()
        self.assertEqual(run.call_count, 1)
        # No child stdout/stderr should accumulate unbounded bytes in RAM.
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertNotIn("capture_output", kwargs)

    def test_invalid_token_blocks_inference(self):
        with patch.object(server.subprocess, "run") as run:
            self.assertEqual(self.request(token="bad")[0], 401)
            self.assertEqual(self.request(consent=None)[0], 403)
            run.assert_not_called()

    def test_non_ascii_bearer_header_returns_401_without_handler_exception(self):
        # BaseHTTPRequestHandler decodes raw header bytes as Latin-1. Python's
        # hmac.compare_digest(str, str) raises TypeError for non-ASCII input;
        # malformed credentials must not crash the handler or run inference.
        head = (
            b"POST /v1/remove-background HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Authorization: Bearer "
        )
        tail = b"\r\nX-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\nContent-Length: 1\r\n\r\nx"
        with patch.object(self.httpd, "handle_error") as unexpected:
            with patch.object(server.subprocess, "run") as inference:
                for byte in (b"\x80", b"\xff"):
                    with self.subTest(byte=byte):
                        response = self.raw_request(head + byte + tail)
                        self.assertIn(b" 401 ", response.split(b"\r\n", 1)[0])
                inference.assert_not_called()
            unexpected.assert_not_called()
        # Rejected malformed credentials cannot poison the next valid request.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_non_png_bad_path_and_empty_payload_refused(self):
        with patch.object(server.subprocess, "run") as run:
            self.assertEqual(self.request(mime="image/jpeg")[0], 415)
            self.assertEqual(self.request(path="/other")[0], 404)
            self.assertEqual(self.request(payload=b"")[0], 413)
            self.assertEqual(self.request(payload=b"broken image")[0], 400)
            run.assert_not_called()

    def test_oversized_png_ihdr_returns_400_without_inference(self):
        # Pillow raises DecompressionBombError at Image.open(), before our
        # own 4 MP dimension guard. A malformed local request must not
        # terminate a handler with an uncaught exception.
        payload = oversized_ihdr_png()
        with self.assertRaises(Image.DecompressionBombError):
            Image.open(io.BytesIO(payload))
        with patch.object(server.subprocess, "run") as inference:
            self.assertEqual(self.request(payload=payload)[0], 400)
            inference.assert_not_called()
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_crc_valid_broken_idat_is_rejected_before_inference(self):
        # PNG chunk/CRC verification alone is insufficient; the full zlib
        # stream must decode before starting CPU model work.
        corrupt = crc_valid_but_undecodable_png()
        with Image.open(io.BytesIO(corrupt)) as image:
            image.verify()  # Demonstrates that the old guard accepted it.
        with patch.object(server.subprocess, "run") as inference:
            self.assertEqual(self.request(payload=corrupt)[0], 400)
            inference.assert_not_called()
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_reject_ambiguous_duplicate_content_length_and_authorization(self):
        image = sample_png()
        head = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
            f"X-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\n"
        ).encode()
        with patch.object(server.subprocess, "run") as run:
            response = self.raw_request(head + f"Content-Length: {len(image)}\r\nContent-Length: {len(image)}\r\n\r\n".encode() + image)
            self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
            response = self.raw_request(head + b"Transfer-Encoding: chunked\r\nContent-Length: 12\r\n\r\n")
            self.assertIn(b" 400 ", response.split(b"\r\n", 1)[0])
            response = self.raw_request(head + f"Authorization: Bearer {TOKEN}\r\nContent-Length: {len(image)}\r\n\r\n".encode() + image)
            self.assertIn(b" 401 ", response.split(b"\r\n", 1)[0])
            run.assert_not_called()

    def test_untrusted_overlong_content_length_is_rejected_without_exception(self):
        # A 5000-digit Content-Length passes isdecimal(), but Python 3.11+
        # rejects int() conversion. The handler must return 413, not crash.
        head = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
            f"X-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\n"
        ).encode()
        with patch.object(self.httpd, "handle_error") as unexpected:
            with patch.object(server.subprocess, "run") as inference:
                for length in (b"9" * 5000, b"0" * 5000, b"25165825", b"+1", b"0"):
                    with self.subTest(length=length[:16]):
                        response = self.raw_request(
                            head + b"Content-Length: " + length + b"\r\n\r\n"
                        )
                        self.assertIn(b" 413 ", response.split(b"\r\n", 1)[0])
                inference.assert_not_called()
            unexpected.assert_not_called()
        # Bad headers must not prevent subsequent authorized processing.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_reject_duplicate_or_conflicting_consent_and_content_type(self):
        # Duplicate yes/yes is still ambiguous: no inference may start until
        # exactly one affirmative consent and one PNG Content-Type are present.
        image = sample_png()
        start = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
        ).encode()
        cases = [
            (b"X-PhotoCraft-Image-Consent: yes\r\n"
             b"X-PhotoCraft-Image-Consent: yes\r\n"
             b"Content-Type: image/png\r\n", 403),
            (b"X-PhotoCraft-Image-Consent: yes\r\n"
             b"X-PhotoCraft-Image-Consent: no\r\n"
             b"Content-Type: image/png\r\n", 403),
            (b"X-PhotoCraft-Image-Consent: yes\r\n"
             b"Content-Type: image/png\r\n"
             b"Content-Type: image/png\r\n", 415),
            (b"X-PhotoCraft-Image-Consent: yes\r\n"
             b"Content-Type: image/png\r\n"
             b"Content-Type: image/jpeg\r\n", 415),
        ]
        with patch.object(server.subprocess, "run") as run:
            for headers, expected in cases:
                with self.subTest(expected=expected, headers=headers):
                    raw = start + headers + f"Content-Length: {len(image)}\r\n\r\n".encode() + image
                    response = self.raw_request(raw)
                    self.assertIn(f" {expected} ".encode(), response.split(b"\r\n", 1)[0])
            run.assert_not_called()

    def test_inference_symlink_output_is_rejected_without_disclosing_local_file(self):
        # Regression: a successful child could create an output symlink to a
        # pre-existing local PNG. is_file(), stat() and PNG validation follow
        # that alias, so the server previously returned unrelated file bytes.
        with tempfile.TemporaryDirectory() as folder:
            unrelated = Path(folder) / "unrelated.png"
            unrelated.write_bytes(sample_png())

            def alias_inference(argv, **_kwargs):
                output = Path(argv[argv.index("--output") + 1])
                output.symlink_to(unrelated)
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(server.subprocess, "run", side_effect=alias_inference) as inference:
                code, headers, body = self.request()
            self.assertEqual(code, 502)
            self.assertEqual(headers["Content-Type"], "text/plain")
            self.assertNotEqual(body, unrelated.read_bytes())
            self.assertEqual(unrelated.read_bytes(), sample_png())
            inference.assert_called_once()

        # Rejecting a bad child output must not poison the next consented job.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_inference_hardlink_output_is_rejected_without_disclosing_local_file(self):
        # Unlike a symlink, a hard link passes is_file() and O_NOFOLLOW.
        # A worker could otherwise return bytes from an unrelated local PNG.
        with tempfile.TemporaryDirectory() as folder:
            unrelated = Path(folder) / "unrelated-private.png"
            Image.new("RGBA", (16, 16), (44, 77, 111, 255)).save(unrelated)
            original = unrelated.read_bytes()

            def hardlink_inference(argv, **_kwargs):
                output = Path(argv[argv.index("--output") + 1])
                output.hardlink_to(unrelated)
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(server.subprocess, "run", side_effect=hardlink_inference) as worker:
                code, headers, body = self.request()
            self.assertEqual(code, 502)
            self.assertEqual(headers["Content-Type"], "text/plain")
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotEqual(body, original)
            self.assertNotIn(str(unrelated).encode(), body)
            self.assertEqual(unrelated.read_bytes(), original)
            worker.assert_called_once()

        # Rejected output must release the worker lock for the next request.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            for _ in range(40):
                code, _, _ = self.request()
                if code != 429:
                    break
                threading.Event().wait(0.03)
            self.assertEqual(code, 200)

    def test_validated_png_cannot_be_swapped_before_http_response(self):
        # Regression: a file replaced immediately after PNG validation used
        # to be returned by Path.read_bytes(), even if it was an unrelated
        # regular PNG with a reused inode. The response now uses a bounded
        # in-memory snapshot, so path changes cannot alter response bytes.
        from validate_output_png import inspect_bytes as original_inspect

        with tempfile.TemporaryDirectory() as folder:
            unrelated = Path(folder) / "unrelated-private.png"
            Image.new("RGBA", (16, 16), (222, 11, 33, 255)).save(unrelated)
            original_bytes = unrelated.read_bytes()

            for replacement in ("symlink", "regular", "missing"):
                with self.subTest(replacement=replacement):
                    worker = {}

                    def inference(argv, **kwargs):
                        worker["path"] = Path(argv[argv.index("--output") + 1])
                        return mock_inference(argv, **kwargs)

                    def swap_after_validation(payload, width, height):
                        alpha = original_inspect(payload, width, height)
                        path = worker["path"]
                        path.unlink()
                        if replacement == "symlink":
                            path.symlink_to(unrelated)
                        elif replacement == "regular":
                            path.write_bytes(original_bytes)
                        return alpha

                    with patch("validate_output_png.inspect_bytes", side_effect=swap_after_validation):
                        with patch.object(server.subprocess, "run", side_effect=inference):
                            # The previous response may precede release of the
                            # one-worker lock; transient 429 is intentional.
                            for attempt in range(40):
                                code, headers, body = self.request()
                                if code != 429:
                                    break
                                threading.Event().wait(0.02)
                    self.assertEqual(code, 200)
                    self.assertEqual(headers["Content-Type"], "image/png")
                    self.assertNotEqual(body, original_bytes)
                    self.assertNotIn(str(unrelated).encode(), body)
                    self.assertEqual(unrelated.read_bytes(), original_bytes)
                    with Image.open(io.BytesIO(body)) as image:
                        image.load()
                        self.assertEqual(image.getpixel((8, 8)), (80, 120, 200, 255))

        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            for attempt in range(40):
                code, _, _ = self.request()
                if code != 429:
                    break
                threading.Event().wait(0.02)
            self.assertEqual(code, 200)

    def test_worker_failure_does_not_return_partial_png(self):
        result = subprocess.CompletedProcess(["no-model"], 2, stdout=b"", stderr=b"private model path")
        with patch.object(server.subprocess, "run", return_value=result):
            code, headers, body = self.request()
        self.assertEqual(code, 502)
        self.assertEqual(headers["Content-Type"], "text/plain")
        self.assertNotIn(b"private", body)

    def test_incomplete_headers_timeout_before_authentication(self):
        # Previously, BaseHTTPRequestHandler waited indefinitely for a
        # client to finish headers; the body-only timeout did not apply.
        # The server must close a stalled pre-auth connection promptly.
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.15):
            with socket.create_connection(self.address, timeout=3) as sock:
                sock.settimeout(2)
                sock.sendall(
                    b"POST /v1/remove-background HTTP/1.1\r\n"
                    b"Host: 127.0.0.1\r\nAuthorization: Bearer "
                )
                try:
                    response = sock.recv(4096)
                except ConnectionResetError:
                    response = b""
                self.assertEqual(response, b"")
        # A stalled header must not prevent the next authorized image.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_expected_header_timeout_does_not_report_unhandled_socket_error(self):
        # Closing an expired pre-auth connection may make Python's HTTP
        # parser attempt a 400/401 response on a dead socket. That is an
        # expected disconnect, not a traceback-worthy server exception.
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.15):
            with patch.object(self.httpd, "handle_error") as unexpected:
                with socket.create_connection(self.address, timeout=3) as sock:
                    sock.settimeout(2)
                    sock.sendall(incomplete_authorization_headers())
                    try:
                        sock.recv(4096)
                    except ConnectionResetError:
                        pass
                threading.Event().wait(0.05)
                unexpected.assert_not_called()

    def test_slow_trickle_pre_auth_headers_hit_absolute_deadline(self):
        # Socket inactivity timeouts are insufficient: a local client can
        # send one byte repeatedly without completing its Authorization line.
        # No inference should start, and the next real request must succeed.
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.35):
            with patch.object(server.subprocess, "run") as inference:
                with socket.create_connection(self.address, timeout=3) as sock:
                    sock.settimeout(1.5)
                    sock.sendall(incomplete_authorization_headers())
                    stop = threading.Event()

                    def trickle():
                        while not stop.wait(0.04):
                            try:
                                sock.sendall(b"x")
                            except OSError:
                                return

                    writer = threading.Thread(target=trickle, daemon=True)
                    writer.start()
                    try:
                        try:
                            reply = sock.recv(4096)
                        except ConnectionResetError:
                            reply = b""
                        self.assertNotIn(b" 200 ", reply.split(b"\r\n", 1)[0])
                    finally:
                        stop.set()
                        writer.join(timeout=2)
                inference.assert_not_called()
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_completed_headers_do_not_timeout_during_cpu_inference(self):
        # Absolute header timer must be cancelled after parsing, not after
        # inference. A valid request can legitimately take longer than 15s.
        def delayed_inference(*args, **kwargs):
            threading.Event().wait(0.65)
            return mock_inference(*args, **kwargs)

        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.35):
            with patch.object(server.subprocess, "run", side_effect=delayed_inference):
                self.assertEqual(self.request()[0], 200)

    def test_slow_trickle_upload_hits_absolute_deadline_and_releases_lock(self):
        # Regression: a client sending a byte every 40 ms previously kept
        # resetting the socket read timeout, holding the inference lock
        # indefinitely without ever delivering its declared PNG body.
        head = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
            f"X-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\n"
            f"Content-Length: 8192\r\n\r\n"
        ).encode()
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.35):
            with patch.object(server.subprocess, "run") as inference:
                with socket.create_connection(self.address, timeout=3) as sock:
                    sock.settimeout(1.5)
                    sock.sendall(head + b"x")
                    stop = threading.Event()

                    def trickle():
                        while not stop.wait(0.04):
                            try:
                                sock.sendall(b"x")
                            except OSError:
                                return

                    writer = threading.Thread(target=trickle, daemon=True)
                    writer.start()
                    try:
                        reply = sock.recv(4096)
                        self.assertIn(b" 408 ", reply.split(b"\r\n", 1)[0])
                    finally:
                        stop.set()
                        writer.join(timeout=2)
                inference.assert_not_called()
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_timeout_releases_server_lock(self):
        head = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
            f"X-PhotoCraft-Image-Consent: yes\r\nContent-Type: image/png\r\n"
            f"Content-Length: 2048\r\n\r\n"
        ).encode()
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.15):
            response = self.raw_request(head + b"partial")
        self.assertIn(b" 408 ", response.split(b"\r\n", 1)[0])
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_unauthenticated_connection_slots_fail_closed(self):
        # A flood of incomplete headers must not create unbounded handler
        # threads/timers before the absolute header timeout expires.
        slots = threading.BoundedSemaphore(1)
        self.httpd._client_slots = slots
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with socket.create_connection(self.address, timeout=3) as sock:
                sock.settimeout(2)
                try:
                    reply = sock.recv(4096)
                except ConnectionResetError:
                    reply = b""
                self.assertEqual(reply, b"")
        finally:
            slots.release()
        # Saturation must not poison later consented requests.
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)

    def test_connection_slot_released_after_authorized_processing(self):
        # A completed inference must return its pre-auth admission slot,
        # otherwise one valid request would permanently exhaust capacity.
        slots = threading.BoundedSemaphore(1)
        self.httpd._client_slots = slots
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            self.assertEqual(self.request()[0], 200)
            for _ in range(100):
                if slots.acquire(blocking=False):
                    slots.release()
                    break
                threading.Event().wait(0.01)
            else:
                self.fail("Completed request leaked a connection slot")
            self.assertEqual(self.request()[0], 200)

    def test_client_disconnect_during_cpu_inference_is_routine_and_server_recovers(self):
        # Android can close or cancel the AI dialog after an upload succeeds
        # but before the local CPU subprocess produces its PNG. A write to
        # that socket must not produce a handler traceback, leak the token,
        # leave the inference lock held, or break later consenting requests.
        started = threading.Event()
        release = threading.Event()

        def delayed_inference(*args, **kwargs):
            started.set()
            if not release.wait(timeout=4):
                raise AssertionError("Mock inference never released")
            return mock_inference(*args, **kwargs)

        payload = sample_png()
        head = (
            f"POST /v1/remove-background HTTP/1.1\r\n"
            f"Host: 127.0.0.1\r\nAuthorization: Bearer {TOKEN}\r\n"
            "X-PhotoCraft-Image-Consent: yes\r\n"
            "Content-Type: image/png\r\n"
            f"Content-Length: {len(payload)}\r\n\r\n"
        ).encode("ascii")
        # Real CRLF, not literal backslash + r/n bytes.
        self.assertIn(b"\r\nAuthorization:", head)
        with patch.object(self.httpd, "handle_error") as unexpected:
            with patch.object(server.subprocess, "run", side_effect=delayed_inference) as inference:
                with socket.create_connection(self.address, timeout=3) as sock:
                    sock.sendall(head + payload)
                    self.assertTrue(started.wait(timeout=3))
                    # Force a disconnect before inference sends its response.
                    sock.shutdown(socket.SHUT_RDWR)
                release.set()
                # Give the handler time to deliver (and reject) its PNG.
                threading.Event().wait(0.15)
                inference.assert_called_once()
            with patch.object(server.subprocess, "run", side_effect=mock_inference):
                # Request-recovery may briefly race the previous handler's
                # finally block. Poll without assuming exact scheduling.
                for _ in range(40):
                    code, _, _ = self.request()
                    if code == 200:
                        break
                    self.assertEqual(code, 429)
                    threading.Event().wait(0.03)
                else:
                    self.fail("Disconnected client left local inference unavailable")
            unexpected.assert_not_called()

    def test_temporary_storage_errors_are_private_and_release_inference_lock(self):
        # A full/unwritable Linux Lab temporary filesystem can fail before
        # the inference subprocess starts. The HTTP handler must not leak a
        # local path or token, crash, or keep the single-worker lock.
        def request_after_backpressure():
            for _ in range(40):
                response = self.request()
                if response[0] != 429:
                    return response
                threading.Event().wait(0.03)
            self.fail("Temporary-storage failure leaked the inference lock")

        failures = (
            (server.tempfile, "TemporaryDirectory", OSError("/home/honor/private/tmp")),
            (server.Path, "write_bytes", OSError("/home/honor/private/input.png")),
        )
        with patch.object(self.httpd, "handle_error") as unexpected:
            for owner, method, failure in failures:
                with self.subTest(stage=method):
                    with patch.object(owner, method, side_effect=failure):
                        with patch.object(server.subprocess, "run") as inference:
                            code, headers, body = request_after_backpressure()
                            self.assertEqual(code, 507)
                            self.assertEqual(headers["Content-Type"], "text/plain")
                            self.assertEqual(headers["Cache-Control"], "no-store")
                            self.assertNotIn(b"/home/honor", body)
                            self.assertNotIn(TOKEN.encode(), body)
                            inference.assert_not_called()
                    # A subsequent independently consented request still works.
                    with patch.object(server.subprocess, "run", side_effect=mock_inference):
                        code, headers, payload = request_after_backpressure()
                        self.assertEqual(code, 200)
                        self.assertEqual(headers["Content-Type"], "image/png")
                        with Image.open(io.BytesIO(payload)) as image:
                            image.load()
                            self.assertEqual(image.size, (16, 16))
            unexpected.assert_not_called()

    def test_cpu_worker_launch_oserror_returns_private_502_and_recovers(self):
        # A missing/unlaunchable Linux Lab Python or bridge raises OSError
        # before subprocess.run returns. Previously this escaped do_POST,
        # closed the socket and logged a handler traceback with local paths.
        # It must be a bounded 502 with no private path or token disclosed.
        for failure in (
            FileNotFoundError(2, "No such file", "/home/honor/private/bridge.py"),
            PermissionError(13, "Permission denied", "/home/honor/private/python"),
        ):
            with self.subTest(error=type(failure).__name__):
                with patch.object(self.httpd, "handle_error") as unexpected:
                    with patch.object(server.subprocess, "run", side_effect=failure) as worker:
                        # A previous valid response can arrive before its
                        # handler finally releases the one-worker lock.
                        # Retry intentional 429 backpressure, never bypass it.
                        for _ in range(40):
                            code, headers, body = self.request()
                            if code != 429:
                                break
                            threading.Event().wait(0.03)
                        self.assertEqual(code, 502)
                        self.assertEqual(headers["Content-Type"], "text/plain")
                        self.assertEqual(headers["Cache-Control"], "no-store")
                        self.assertNotIn(b"/home/honor", body)
                        self.assertNotIn(TOKEN.encode(), body)
                        worker.assert_called_once()
                    unexpected.assert_not_called()
                # The failed request must release the inference lock and
                # leave the local service usable for fresh per-image consent.
                with patch.object(server.subprocess, "run", side_effect=mock_inference):
                    for _ in range(40):
                        code, _, _ = self.request()
                        if code == 200:
                            break
                        self.assertEqual(code, 429)
                        threading.Event().wait(0.03)
                    else:
                        self.fail("Worker launch failure leaked inference lock")

    def test_cpu_timeout_returns_504_and_next_job_recovers(self):
        # A stalled CPU subprocess must produce a bounded error, drop its
        # temporary files and release the one-worker lock for the next image.
        with patch.object(
            server.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd=["mock-inference"], timeout=180),
        ) as inference:
            code, headers, body = self.request()
            self.assertEqual(code, 504)
            self.assertEqual(headers["Content-Type"], "text/plain")
            self.assertNotIn(TOKEN.encode(), body)
            inference.assert_called_once()
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            code, headers, payload = self.request()
            self.assertEqual(code, 200)
            self.assertEqual(headers["Content-Type"], "image/png")
            with Image.open(io.BytesIO(payload)) as img:
                img.load()
                self.assertEqual(img.size, (16, 16))

    def test_server_restart_requires_fresh_token_and_recovers(self):
        # Simulate manually restarting the Linux Lab server without any model
        # weights. Tokens are ephemeral and must not survive a new server.
        new_token = "different_restart_token_longer_than_32_characters"
        restarted = server.LoopbackHTTPServer(
            ("127.0.0.1", 0), server.make_handler(new_token)
        )
        worker = threading.Thread(
            target=restarted.serve_forever, daemon=True
        )
        worker.start()

        def on_restarted(token):
            conn = http.client.HTTPConnection(*restarted.server_address, timeout=5)
            try:
                conn.request(
                    "POST", "/v1/remove-background", body=sample_png(),
                    headers={
                        "Authorization": "Bearer " + token,
                        "X-PhotoCraft-Image-Consent": "yes",
                        "Content-Type": "image/png",
                    },
                )
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()

        try:
            with patch.object(server.subprocess, "run", side_effect=mock_inference) as inference:
                old_code, old_body = on_restarted(TOKEN)
                self.assertEqual(old_code, 401)
                self.assertNotIn(new_token.encode(), old_body)
                self.assertEqual(inference.call_count, 0)
                new_code, new_png = on_restarted(new_token)
                self.assertEqual(new_code, 200)
                with Image.open(io.BytesIO(new_png)) as image:
                    image.load()
                    self.assertEqual(image.size, (16, 16))
                self.assertEqual(inference.call_count, 1)
        finally:
            restarted.shutdown()
            restarted.server_close()
            worker.join(timeout=3)
        with patch.object(server.subprocess, "run", side_effect=mock_inference):
            # Original running service stays isolated and usable.
            self.assertEqual(self.request()[0], 200)

    def test_sequential_consent_jobs_do_not_exhaust_inference_lock(self):
        # Multiple normal jobs must not leak worker state. Actual long-running
        # tablet memory behavior remains a separate physical-device gate.
        with patch.object(server.subprocess, "run", side_effect=mock_inference) as run:
            for _ in range(12):
                # The HTTP client can receive a complete response before the
                # worker's finally block has released its single-inference
                # lock. A brief 429 is intentional backpressure, not failure;
                # retry within a bound rather than removing server safety.
                for attempt in range(40):
                    code, headers, payload = self.request()
                    if code == 200:
                        break
                    self.assertEqual(code, 429)
                    threading.Event().wait(0.02)
                else:
                    self.fail("Sequential request failed to recover from busy worker")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertGreater(len(payload), 30)
            self.assertEqual(run.call_count, 12)

    def test_only_one_inference_runs_at_a_time(self):
        entered = threading.Event()
        release = threading.Event()

        def held_inference(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=4))
            return mock_inference(*args, **kwargs)

        with patch.object(server.subprocess, "run", side_effect=held_inference):
            with ThreadPoolExecutor(max_workers=1) as pool:
                first = pool.submit(self.request)
                try:
                    self.assertTrue(entered.wait(timeout=3))
                    self.assertEqual(self.request()[0], 429)
                finally:
                    release.set()
                self.assertEqual(first.result(timeout=5)[0], 200)


if __name__ == "__main__":
    unittest.main()
