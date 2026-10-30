#!/usr/bin/env python3
"""Offline tests for the actual U2NetP file bridge (no model download or inference)."""
from __future__ import annotations
import importlib.util
import io
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("local_background_bridge", HERE / "local_background_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class SidecarTests(unittest.TestCase):
    def make_png(self, path):
        Image.new("RGBA", (16, 16), (50, 80, 120, 255)).save(path)

    def test_consent_required_before_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            with self.assertRaisesRegex(ValueError, "consent"):
                bridge.run(source, output, False)
            self.assertFalse(output.exists())

    def test_valid_png_passes_pillow_verification_and_reaches_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            with patch.object(bridge.subprocess, "run", side_effect=RuntimeError("MOCK_REACHED")) as runner:
                with self.assertRaisesRegex(RuntimeError, "MOCK_REACHED"):
                    bridge.run(source, output, True)
            runner.assert_called_once()
            kwargs = runner.call_args.kwargs
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertNotIn("capture_output", kwargs)
            self.assertFalse(output.exists())

    def test_rejects_non_png_before_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.jpg", Path(folder) / "output.png"
            Image.new("RGB", (16, 16)).save(source)
            with patch.object(bridge.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "Only PNG"):
                    bridge.run(source, output, True)
                runner.assert_not_called()

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "new PNG"):
                bridge.run(source, output, True)
            self.assertEqual(output.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
