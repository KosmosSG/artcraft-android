#!/usr/bin/env python3
"""Offline, local-only protocol tests for PhotoCraft OpenFill Linux Lab.
No network outside 127.0.0.1, no model, downloads or ComfyUI required.
"""
import http.client
import io
import json
import struct
import threading
import unittest
from http.server import ThreadingHTTPServer

from PIL import Image
from openfill_local_server import decode_request, make_handler, png_bytes


def request_payload(mode="fill", source=(2, 2), out=None, prompt=None, mask=None, x=0, y=0):
    out = out or source
    if mode == "create":
        source = (0, 0)
    if prompt is None:
        prompt = "" if mode == "remove" else "watercolor flower"
    meta = {
        "operation": mode,
        "width": out[0],
        "height": out[1],
        "source_width": source[0],
        "source_height": source[1],
        "offset_x": x, "offset_y": y,
        "prompt": prompt, "model": "licensed-model",
    }
    hdr = json.dumps(meta).encode()
    pixels = (Image.new("RGBA", source, (10, 50, 100, 255)).tobytes()
              if mode != "create" else b"")
    selected = ((mask if mask is not None else b"\x00\xff\x80\x00")
                if mode in ("fill", "remove") else b"")
    return struct.pack(">I", len(hdr)) + hdr + pixels + selected


class ContractTests(unittest.TestCase):
    def test_fill_preserves_feathered_mask(self):
        header, source, mask = decode_request(request_payload())
        self.assertEqual(header["operation"], "fill")
        self.assertEqual(source.size, (2, 2))
        self.assertEqual(list(mask.getdata()), [0, 255, 128, 0])

    def test_remove_has_no_prompt_and_requires_mask(self):
        self.assertEqual(decode_request(request_payload(mode="remove"))[0]["prompt"], "")
        with self.assertRaises(ValueError):
            decode_request(request_payload(mode="remove", prompt="inject"))
        with self.assertRaises(ValueError):
            decode_request(request_payload(mode="remove", mask=b"\x00" * 4))

    def test_expand_keeps_original_pixels_and_requires_added_space(self):
        h, src, mask = decode_request(request_payload(
            mode="expand", source=(2, 2), out=(4, 3), x=1, y=0))
        self.assertEqual(src.size, (4, 3))
        self.assertEqual(h["_source_image"].size, (2, 2))
        self.assertEqual(src.getpixel((1, 0)), (10, 50, 100, 255))
        self.assertEqual(mask.getpixel((1, 0)), 0)
        self.assertEqual(mask.getpixel((0, 0)), 255)
        with self.assertRaises(ValueError):
            decode_request(request_payload(mode="expand", out=(2, 2)))

    def test_create_does_not_require_or_capture_a_document(self):
        h, src, mask = decode_request(request_payload(mode="create"))
        self.assertIsNone(src)
        self.assertIsNone(mask)
        self.assertEqual(h["operation"], "create")
        with self.assertRaises(ValueError):
            decode_request(request_payload(mode="create", prompt=""))

    def test_bad_request_sizes_and_unexpected_input_fail_closed(self):
        for bad in (b"", b"\x00\x00\x00\x04", request_payload()[:-1],
                    request_payload(mode="create", out=(5000, 5000)),
                    request_payload(mode="fill", prompt="bad\ncontrol")):
            with self.subTest(length=len(bad)):
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    decode_request(bad)

    def test_loopback_server_requires_token_and_per_request_consent(self):
        count = []
        def synthetic(header, _image, _mask):
            count.append(header["operation"])
            return png_bytes(Image.new("RGBA", (2, 2), (255, 0, 0, 255)))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler("abc" * 16, synthetic))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        data = request_payload()
        def post(auth, consent=True):
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {
                "Authorization": auth,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data)),
            }
            if consent:
                headers["X-PhotoCraft-Image-Consent"] = "yes"
            try:
                conn.request("POST", "/v1/openfill", data, headers)
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()
        try:
            self.assertEqual(post("Bearer wrong")[0], 401)
            self.assertEqual(post("Bearer " + "abc" * 16, False)[0], 403)
            self.assertEqual(count, [])
            code, result = post("Bearer " + "abc" * 16)
            self.assertEqual(code, 200)
            self.assertTrue(result.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(count, ["fill"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
