#!/usr/bin/env python3
"""Synthetic loopback-only tests for PhotoCraft's Linux Lab ComfyUI probe."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

import linux_lab_comfy_probe as probe


class Handler(BaseHTTPRequestHandler):
    mode = "good"

    def do_GET(self):
        if self.path not in ("/system_stats", "/models/checkpoints"):
            self.send_error(404)
            return
        if self.mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "https://example.com/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.mode == "huge":
            body = b"x" * (probe.MAX_REPLY + 1)
        elif self.mode == "invalid":
            body = b"{"
        elif self.path == "/system_stats":
            body = b'{"system":{"os":"linux"},"devices":[]}'
        elif self.mode == "bad_catalog":
            body = b'{"checkpoints": ["foo"]}'
        else:
            body = b'["local-model.safetensors"]'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer((probe.LOOPBACK, 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        Handler.mode = "good"

    def test_check_success_is_not_generation_success(self):
        result = probe.check(port=self.port)
        self.assertEqual(result["status"], "comfyui_reachable")
        self.assertEqual(result["checkpoint_count"], 1)
        self.assertFalse(result["generation_ready"])
        self.assertEqual(result["endpoint"], f"http://127.0.0.1:{self.port}")

    def test_refuses_arbitrary_routes(self):
        with self.assertRaises(ValueError):
            probe.read_json("/prompt", port=self.port)

    def test_does_not_follow_redirects(self):
        Handler.mode = "redirect"
        with self.assertRaises(RuntimeError):
            probe.check(port=self.port)

    def test_bounded_response(self):
        Handler.mode = "huge"
        with self.assertRaises(RuntimeError):
            probe.check(port=self.port)

    def test_invalid_json_is_not_a_success(self):
        Handler.mode = "invalid"
        with self.assertRaises(json.JSONDecodeError):
            probe.check(port=self.port)

    def test_malformed_catalog_is_not_ready(self):
        Handler.mode = "bad_catalog"
        with self.assertRaises(RuntimeError):
            probe.check(port=self.port)


if __name__ == "__main__":
    unittest.main()
