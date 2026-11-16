#!/usr/bin/env python3
"""PhotoCraft Android -> Linux Lab OpenFill inference, opt-in, loopback only.

This is a separate Linux Lab process, NOT an Android background service. It
imports official OpenFill Python workflow builders from the owner's OpenFill
checkout and connects only to ComfyUI at 127.0.0.1:8188. It never downloads
models or sends files to the cloud. Requires an installed compatible model
and explicit consent for EACH request. No prompts/images in logs/on disk.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import io
import json
from pathlib import Path
import secrets
import socket
import struct
import threading
import time

from PIL import Image

MAX_PIXELS = 20_000_000
MAX_BODY = 105 * 1024 * 1024
MAX_RESULT = 96 * 1024 * 1024
MAX_PROMPT = 2000
HEADER_LIMIT = 8192
OPERATIONS = ("fill", "remove", "expand", "create")
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def checked_size(w: object, h: object) -> tuple[int, int]:
    if type(w) is not int or type(h) is not int:
        raise ValueError("Expected integer dimensions")
    if not 1 <= w <= 20_000 or not 1 <= h <= 20_000 or w * h > MAX_PIXELS:
        raise ValueError("Dimensions exceed 20 MP")
    return w, h


def decode_request(body: bytes) -> tuple[dict, Image.Image | None, Image.Image | None]:
    if len(body) < 4 or len(body) > MAX_BODY:
        raise ValueError("Invalid request size")
    header_len = struct.unpack(">I", body[:4])[0]
    if not 1 <= header_len <= HEADER_LIMIT or 4 + header_len > len(body):
        raise ValueError("Invalid metadata size")
    header = json.loads(body[4:4 + header_len])
    if not isinstance(header, dict):
        raise ValueError("Invalid metadata structure")
    mode = header.get("operation")
    if mode not in OPERATIONS:
        raise ValueError("Unsupported OpenFill operation")
    output = checked_size(header.get("width"), header.get("height"))
    source = checked_size(header.get("source_width"), header.get("source_height")) if mode != "create" else None
    prompt = header.get("prompt")
    if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT or any(ord(c) < 32 for c in prompt):
        raise ValueError("Invalid prompt")
    if mode in ("fill", "create") and not prompt.strip():
        raise ValueError("A prompt is required")
    if mode == "remove" and prompt.strip():
        raise ValueError("Remove Object requires an empty prompt")
    model = header.get("model")
    if (not isinstance(model, str) or not 1 <= len(model) <= 80 or
            any(not (c.isascii() and (c.isalnum() or c in "-_.")) for c in model)):
        raise ValueError("Invalid model identifier")
    x, y = header.get("offset_x"), header.get("offset_y")
    if type(x) is not int or type(y) is not int or x < 0 or y < 0:
        raise ValueError("Invalid source offsets")
    pixels = b""
    mask = b""
    source_png = None
    if source:
        sw, sh = source
        n = sw * sh
        count = n * 4
        mask_count = n if mode in ("fill", "remove") else 0
        raw = body[4 + header_len:]
        if len(raw) != count + mask_count:
            raise ValueError("Source RGBA and mask buffers have incorrect lengths")
        pixels = raw[:count]
        mask = raw[count:]
        source_png = Image.frombytes("RGBA", (sw, sh), pixels)
    elif len(body) != 4 + header_len:
        raise ValueError("Create must not include source pixels")
    if mode in ("fill", "remove"):
        if output != source or x or y or not mask or not any(mask):
            raise ValueError("A real nonempty canvas selection is required")
        selection = Image.frombytes("L", source, mask)
    elif mode == "expand":
        assert source is not None
        if output == source or output[0] < source[0] or output[1] < source[1]:
            raise ValueError("Expanded canvas must be bigger")
        if x > output[0] - source[0] or y > output[1] - source[1]:
            raise ValueError("The original image would be cropped")
        header["_source_image"] = source_png.copy()
        full = Image.new("RGBA", output, (0, 0, 0, 0))
        full.paste(source_png, (x, y))
        source_png = full
        selection = Image.new("L", output, 255)
        selection.paste(0, (x, y, x + source[0], y + source[1]))
    else:
        if x or y:
            raise ValueError("Create may not include source offsets")
        selection = None
    return header, source_png, selection


def png_bytes(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()


def run_openfill(
    header: dict, source: Image.Image | None, selection: Image.Image | None,
    *, catalog_path: Path, models_root: Path, nodes_dir: Path, comfy_url: str,
) -> bytes:
    # Imported lazily so source/contract tests need only Pillow. Linux Lab
    # must install the official OpenFill companion in this Python environment.
    from openfill import catalog as cat
    from openfill.backend import InpaintRequest, Txt2ImgRequest, Sampling
    from openfill.backends.comfy import ComfyBackend

    mode = header["operation"]
    operation = {"fill": "fill", "remove": "remove", "expand": "expand", "create": "txt2img"}[mode]
    entries = cat.load_catalog(path=catalog_path)
    allowed = cat.runnable_installed(entries, models_root, nodes_dir, operation=operation)
    entry = next((e for e in allowed if e.id == header["model"]), None)
    if entry is None:
        raise RuntimeError("The selected licensed OpenFill model/nodes are not installed")
    if entry.gated:
        raise RuntimeError("Gated model license must be accepted explicitly before use")
    spec = cat.model_spec_for(entry, entries, models_root=models_root)
    backend = ComfyBackend(url=comfy_url, request_timeout=900)
    width, height = checked_size(header["width"], header["height"])
    prompt = header["prompt"] if mode != "remove" else ""
    sampling = Sampling(steps=20 if mode != "remove" else 10, batch=1)
    if mode == "create":
        request = Txt2ImgRequest(width=width, height=height, prompt=prompt,
                                 negative="", model=spec, sampling=sampling)
        result = backend.txt2img(request)
    else:
        assert source is not None and selection is not None
        # The official OpenFill workflow scales its own working canvas.
        # Constrain the expensive inference resolution without dropping the
        # full-size source/result geometry.
        edge = max(width, height)
        scale = min(1.0, 1024.0 / edge)
        work_width = max(64, int(round(width * scale / 8)) * 8)
        work_height = max(64, int(round(height * scale / 8)) * 8)
        request = InpaintRequest(
            image_png=png_bytes(source),
            mask_png=png_bytes(selection),
            width=width, height=height,
            work_width=work_width, work_height=work_height,
            prompt=prompt, negative="", model=spec, sampling=sampling,
            mode="expand" if mode == "expand" else "fill",
        )
        result = backend.outpaint(request) if mode == "expand" else backend.inpaint(request)
    if not result.images:
        raise RuntimeError("OpenFill returned no generated output")
    data = result.images[0]
    if not 0 < len(data) <= MAX_RESULT:
        raise RuntimeError("OpenFill output size is invalid")
    with Image.open(io.BytesIO(data)) as output:
        if output.format != "PNG":
            raise RuntimeError("OpenFill must return a PNG")
        output.load()
        if output.size != (width, height):
            raise RuntimeError("OpenFill output dimensions do not match the request")
        rgba = output.convert("RGBA")
        if mode == "expand":
            # Never let inpainting alter a single original pixel. A separate
            # transparent outpaint layer is constructed by the Android adapter.
            original = header.get("_source_image")
            # The original source is not sent in metadata. The handler supplies
            # it from the immutable request before expand canvas composition.
            if isinstance(original, Image.Image):
                rgba.paste(original, (header["offset_x"], header["offset_y"]))
        return png_bytes(rgba)


def make_handler(token: str, inference):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "PhotoCraftOpenFillLocal/0.1"
        protocol_version = "HTTP/1.0"

        def log_message(self, *_args):
            # Do not log prompts, document names, tokens or image contents.
            pass

        def reply(self, code: int, data: bytes, mime="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            return self.reply(404, b"Not found")

        def do_POST(self):
            if self.path != "/v1/openfill":
                return self.reply(404, b"Not found")
            auth = self.headers.get_all("Authorization", [])
            if (len(auth) != 1 or not auth[0].isascii() or
                    not hmac.compare_digest(auth[0], "Bearer " + token)):
                return self.reply(401, b"Invalid session token")
            if self.headers.get_all("X-PhotoCraft-Image-Consent", []) != ["yes"]:
                return self.reply(403, b"Per-image consent is required")
            if self.headers.get_all("Content-Type", []) != ["application/octet-stream"]:
                return self.reply(415, b"Wrong content type")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                return self.reply(400, b"Invalid upload framing")
            if not lengths[0].isascii() or not lengths[0].isdecimal() or len(lengths[0]) > 9:
                return self.reply(413, b"Invalid upload length")
            length = int(lengths[0])
            if not 5 <= length <= MAX_BODY:
                return self.reply(413, b"Upload exceeds limit")
            if not lock.acquire(blocking=False):
                return self.reply(429, b"One generation at a time")
            try:
                # Absolute deadline (not a per-read timeout alone).
                end = time.monotonic() + 50
                chunks = []
                left = length
                while left:
                    remaining = end - time.monotonic()
                    if remaining <= 0:
                        return self.reply(408, b"Upload timed out")
                    self.connection.settimeout(min(remaining, 5))
                    try:
                        chunk = self.rfile.read1(min(64 * 1024, left))
                    except (socket.timeout, OSError):
                        return self.reply(408, b"Upload timed out")
                    if not chunk:
                        return self.reply(400, b"Truncated upload")
                    left -= len(chunk)
                    chunks.append(chunk)
                try:
                    header, image, mask = decode_request(b"".join(chunks))
                    data = inference(header, image, mask)
                except (ValueError, TypeError, json.JSONDecodeError):
                    return self.reply(400, b"Invalid OpenFill request")
                except Exception:
                    # No raw exception content: a model error may contain
                    # sensitive paths or model/token information.
                    return self.reply(502, b"OpenFill model unavailable or generation failed")
                if not data or len(data) > MAX_RESULT:
                    return self.reply(502, b"Invalid model output")
                return self.reply(200, data, "image/png")
            finally:
                lock.release()

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18794)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--models-root", type=Path, required=True)
    parser.add_argument("--custom-nodes", type=Path, required=True)
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    options = parser.parse_args()
    if not 1024 <= options.port <= 65535:
        parser.error("Port outside valid range")
    if options.comfy_url != "http://127.0.0.1:8188":
        parser.error("Only Linux Lab loopback ComfyUI at 127.0.0.1:8188 is permitted")
    if not options.catalog.is_file() or not options.models_root.is_dir():
        parser.error("OpenFill model catalog and ComfyUI models must already exist")
    token = secrets.token_urlsafe(32)
    def infer(header, img, mask):
        return run_openfill(header, img, mask, catalog_path=options.catalog,
                            models_root=options.models_root, nodes_dir=options.custom_nodes,
                            comfy_url=options.comfy_url)
    server = ThreadingHTTPServer(("127.0.0.1", options.port), make_handler(token, infer))
    server.daemon_threads = True
    print(f"PhotoCraft OpenFill Linux Lab: http://127.0.0.1:{options.port}/v1/openfill")
    print("Temporary local token (do not share):", token, flush=True)
    print("No cloud service, model download or public listener. Ctrl+C stops the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
