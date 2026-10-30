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
import threading
import unittest
from unittest.mock import patch

from PIL import Image

SOURCE = Path(__file__).with_name("loopback_u2netp_server.py")
spec = importlib.util.spec_from_file_location("photocraft_u2netp_http", SOURCE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

TOKEN = "temporary_test_token_with_at_least_32_characters"


def sample_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (20, 80, 160, 255)).save(buf, format="PNG")
    return buf.getvalue()


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

    def test_non_png_bad_path_and_empty_payload_refused(self):
        with patch.object(server.subprocess, "run") as run:
            self.assertEqual(self.request(mime="image/jpeg")[0], 415)
            self.assertEqual(self.request(path="/other")[0], 404)
            self.assertEqual(self.request(payload=b"")[0], 413)
            self.assertEqual(self.request(payload=b"broken image")[0], 400)
            run.assert_not_called()

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

    def test_slow_trickle_pre_auth_headers_hit_absolute_deadline(self):
        # Socket inactivity timeouts are insufficient: a local client can
        # send one byte repeatedly without completing its Authorization line.
        # No inference should start, and the next real request must succeed.
        with patch.object(server, "REQUEST_READ_TIMEOUT", 0.35):
            with patch.object(server.subprocess, "run") as inference:
                with socket.create_connection(self.address, timeout=3) as sock:
                    sock.settimeout(1.5)
                    sock.sendall(
                        b"POST /v1/remove-background HTTP/1.1\\r\\n"
                        b"Host: 127.0.0.1\\r\\nAuthorization: Bearer "
                    )
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
                        self.assertNotIn(b" 200 ", reply.split(b"\\r\\n", 1)[0])
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
