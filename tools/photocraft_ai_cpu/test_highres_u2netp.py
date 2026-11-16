"""Bounded full-size U2NetP alpha proxy synthetic tests: no model or user documents."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import highres_u2netp as hr


class Tests(unittest.TestCase):
    def test_owner_dimensions(self):
        self.assertEqual(hr.proxy_dimensions(4167, 4167), (1536, 1536))
        self.assertEqual(hr.proxy_dimensions(1000, 1000), (1000, 1000))
        with self.assertRaises(ValueError):
            hr.proxy_dimensions(5000, 5000)

    def test_preserves_original_rgb_and_existing_transparency(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d)/"original.png", Path(d)/"new.png"
            original = Image.new("RGBA", (96, 72), (23, 65, 124, 200))
            original.putpixel((0, 0), (200, 50, 100, 0))
            original.save(src)
            def infer(inp, out):
                with Image.open(inp) as image:
                    self.assertLessEqual(image.width * image.height, 256)
                    Image.new("RGBA", image.size, (0, 0, 0, 255)).save(out)
            with patch.object(hr, "PROXY_PIXELS", 256):
                hr.process_high_resolution(src, dst, infer)
            with Image.open(dst) as image:
                image.load()
                self.assertEqual(image.size, original.size)
                self.assertEqual(image.getpixel((30, 20)), (23, 65, 124, 200))
                self.assertEqual(image.getpixel((0, 0)), (200, 50, 100, 0))
            self.assertTrue(src.is_file())

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d)/"original.png", Path(d)/"new.png"
            Image.new("RGB", (96, 72)).save(src)
            dst.write_bytes(b"keep")
            with patch.object(hr, "PROXY_PIXELS", 256):
                with self.assertRaises(ValueError):
                    hr.process_high_resolution(src, dst, lambda *_: None)
            self.assertEqual(dst.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
