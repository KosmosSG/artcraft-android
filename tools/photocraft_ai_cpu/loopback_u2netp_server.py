#!/usr/bin/env python3
"""Opt-in, loopback-only U2NetP HTTP transport for PhotoCraft AI experiments.

Run inside the dedicated Linux Lab CPU venv for the consent-gated PhotoCraft AI Preview.
The caller must supply a random bearer token and explicit per-image consent.
No model downloads, public bind, filesystem paths or persistent image storage.
"""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import io
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from PIL import Image

MAX_BYTES = 24 * 1024 * 1024
MAX_PIXELS = 4_000_000
MAX_RESULT = 32 * 1024 * 1024
# A client that does not finish uploading must never monopolize inference.
REQUEST_READ_TIMEOUT = 15
BRIDGE = Path(__file__).resolve().with_name("local_background_bridge.py")


def verify_input(payload: bytes) -> tuple[int, int]:
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("Input size outside allowed range")
    with Image.open(io.BytesIO(payload)) as image:
        if image.format != "PNG":
            raise ValueError("Only PNG input is accepted")
        width, height = image.size
        if width < 1 or height < 1 or width * height > MAX_PIXELS:
            raise ValueError("Image dimensions outside allowed range")
        image.verify()
    return width, height


def make_handler(token: str):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "PhotoCraftLocalCPU/0.2"
        # Python normally sends HTTP/1.0; Android supports 1.0 and 1.1.
        protocol_version = "HTTP/1.0"

        def log_message(self, fmt, *args):
            # Never log credentials, user paths or image contents.
            pass

        def reply(self, code: int, body: bytes, mime: str = "text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.reply(404, b"Not found")

        def do_POST(self):
            if self.path != "/v1/remove-background":
                return self.reply(404, b"Not found")
            # Reject duplicate credentials rather than allowing the HTTP
            # parser to silently choose one of several Authorization values.
            auth_values = self.headers.get_all("Authorization", [])
            if len(auth_values) != 1 or not hmac.compare_digest(
                auth_values[0], "Bearer " + token,
            ):
                return self.reply(401, b"Unauthorized")
            # Consent must be an unambiguous, single affirmative header.
            # BaseHTTPRequestHandler.headers.get() silently chooses the first
            # of duplicated fields, which can conceal a conflicting value.
            consents = self.headers.get_all("X-PhotoCraft-Image-Consent", [])
            if consents != ["yes"]:
                return self.reply(403, b"Per-image consent required")
            content_types = self.headers.get_all("Content-Type", [])
            if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip() != "image/png":
                return self.reply(415, b"PNG required")
            # Explicit length and no transfer-coding ambiguity. Never accept
            # multiple Content-Length headers or HTTP chunked request bodies.
            sizes = self.headers.get_all("Content-Length", [])
            if len(sizes) != 1 or self.headers.get("Transfer-Encoding") is not None:
                return self.reply(400, b"Ambiguous input framing")
            raw_size = sizes[0]
            if not raw_size.isdecimal() or not (1 <= int(raw_size) <= MAX_BYTES):
                return self.reply(413, b"Invalid input size")
            if not lock.acquire(blocking=False):
                return self.reply(429, b"Another inference is running")
            try:
                self.connection.settimeout(REQUEST_READ_TIMEOUT)
                try:
                    payload = self.rfile.read(int(raw_size))
                except (TimeoutError, ConnectionError):
                    # A stalled or disconnected client must release the lock.
                    try:
                        return self.reply(408, b"Image upload timed out")
                    except OSError:
                        return
                if len(payload) != int(raw_size):
                    return self.reply(400, b"Truncated image")
                try:
                    width, height = verify_input(payload)
                except (ValueError, OSError, SyntaxError):
                    return self.reply(400, b"Invalid image")
                with tempfile.TemporaryDirectory(prefix="photocraft-u2netp-") as folder:
                    source = Path(folder) / "input.png"
                    output = Path(folder) / "output.png"
                    source.write_bytes(payload)
                    try:
                        completed = subprocess.run(
                            [sys.executable, str(BRIDGE), "--input", str(source),
                             "--output", str(output), "--consent-local-processing"],
                            capture_output=True, timeout=180, check=False,
                        )
                    except subprocess.TimeoutExpired:
                        return self.reply(504, b"CPU inference timed out")
                    if completed.returncode != 0 or not output.is_file():
                        return self.reply(502, b"CPU inference or validation failed")
                    if output.stat().st_size > MAX_RESULT:
                        return self.reply(502, b"Output exceeds safety limit")
                    from validate_output_png import inspect
                    try:
                        inspect(output, width, height)
                    except Exception:
                        return self.reply(502, b"Output PNG validation failed")
                    return self.reply(200, output.read_bytes(), "image/png")
            finally:
                lock.release()

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18793)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        assert verify_input(_synthetic_png()) == (16, 16)
        for bad in (b"", b"not a png"):
            try:
                verify_input(bad)
            except (ValueError, OSError, SyntaxError):
                pass
            else:
                raise AssertionError("Invalid input accepted")
        print("PASS: bounded PNG input validation")
        return
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(token))
    print(f"Local-only U2NetP endpoint: http://127.0.0.1:{args.port}/v1/remove-background")
    print("Temporary session bearer token (keep private):", token, flush=True)
    print("Linux Lab must remain running; Ctrl+C stops server. No public binding.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _synthetic_png():
    image = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
