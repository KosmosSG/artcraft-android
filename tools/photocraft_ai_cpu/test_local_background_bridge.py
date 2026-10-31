#!/usr/bin/env python3
"""Offline tests for the actual U2NetP file bridge (no model download or inference)."""
from __future__ import annotations
import importlib.util
import io
import subprocess
from pathlib import Path
import tempfile
import unittest
import zlib
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

    def test_oversized_png_ihdr_is_controlled_validation_error(self):
        # A CRC-correct 400 MP IHDR triggers Pillow's early bomb check,
        # even though the compressed file is tiny. No CPU inference.
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            data = source.read_bytes()
            marker = data.index(b"IHDR")
            dimensions = marker + 4
            data = data[:dimensions] + (20_000).to_bytes(4, "big") * 2 + data[dimensions + 8:]
            crc_at = marker + 4 + 13
            source.write_bytes(data[:crc_at] + zlib.crc32(data[marker:crc_at]).to_bytes(4, "big") + data[crc_at + 4:])
            with patch.object(bridge.subprocess, "run") as inference:
                with self.assertRaisesRegex(ValueError, "dimensions outside safety limit"):
                    bridge.run(source, output, True)
                inference.assert_not_called()
            self.assertFalse(output.exists())

    def test_crc_valid_but_undecodable_png_never_starts_inference(self):
        # The old image.verify() guard accepted CRC-correct PNGs whose
        # compressed IDAT stream fails only during actual pixel decoding.
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            data = source.read_bytes()
            chunk = data.index(b"IDAT") - 4
            length = int.from_bytes(data[chunk:chunk + 4], "big")
            start, end = chunk + 8, chunk + 8 + length
            self.assertGreaterEqual(length, 3)
            invalid_zlib = b"\x78\x9c" + b"\xff" * (length - 2)
            checksum = zlib.crc32(b"IDAT" + invalid_zlib).to_bytes(4, "big")
            source.write_bytes(data[:start] + invalid_zlib + checksum + data[end + 4:])
            with Image.open(io.BytesIO(source.read_bytes())) as image:
                image.verify()  # CRC passes despite invalid deflate stream.
            with patch.object(bridge.subprocess, "run") as runner:
                with self.assertRaises((OSError, ValueError)):
                    bridge.run(source, output, True)
                runner.assert_not_called()
            self.assertFalse(output.exists())

    def test_refuses_dangling_output_symlink_before_inference(self):
        # resolve() follows dangling symlinks, so an absent target previously
        # passed exists() and could be created outside the requested output.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "input.png"
            output = root / "output.png"
            outside = root / "different-location.png"
            self.make_png(source)
            output.symlink_to(outside)
            self.assertFalse(outside.exists())
            with patch.object(bridge.subprocess, "run") as inference:
                with self.assertRaisesRegex(ValueError, "symlink"):
                    bridge.run(source, output, True)
                inference.assert_not_called()
            self.assertTrue(output.is_symlink())
            self.assertFalse(outside.exists())

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
