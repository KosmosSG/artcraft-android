"""Regression tests for the black border reported on the actual MagicPad launcher."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from PIL import Image, ImageDraw
import launcher_icon

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/designcraft/icon/dc-user-20261023.webp"


class LauncherIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        launcher_icon.generate(SOURCE, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_unchanged_and_legacy_corners_are_transparent(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), launcher_icon.APPROVED_SHA256)
        for density, size in launcher_icon.DENSITIES.items():
            with Image.open(self.output / f"mipmap-{density}/ic_launcher.png") as image:
                self.assertEqual(image.size, (size, size))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertGreater(image.getpixel((size//2, 2))[0], 50)

    def test_adaptive_background_and_both_launcher_masks_have_no_black_ring(self):
        import re
        xml = (self.output / "drawable/ic_launcher_background.xml").read_text()
        color = re.search(r'android:color="(#[A-F0-9]{6})"', xml)[1]
        with Image.open(self.output / "drawable-xxxhdpi/ic_launcher_foreground.png") as foreground:
            composed = Image.new("RGBA", foreground.size, color)
            composed.alpha_composite(foreground)
            viewport = composed.crop((72, 72, 360, 360))
        for circle in (False, True):
            mask = Image.new("L", viewport.size)
            draw = ImageDraw.Draw(mask)
            if circle:
                draw.ellipse((0, 0, 287, 287), fill=255)
            else:
                draw.rounded_rectangle((0, 0, 287, 287), radius=62, fill=255)
            visible = [p for p, a in zip(viewport.getdata(), mask.getdata()) if a]
            self.assertTrue(all(max(p[:3]) > 32 for p in visible))

    def test_both_adaptive_entries_use_the_reviewed_layers(self):
        for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
            xml = (self.output / "mipmap-anydpi-v26" / name).read_text()
            self.assertIn('@drawable/ic_launcher_background', xml)
            self.assertIn('@drawable/ic_launcher_foreground', xml)

    def test_glass_lettering_fits_inside_circular_launcher(self):
        with Image.open(self.output / "drawable-xxxhdpi/ic_launcher_foreground.png") as foreground:
            highlights = [(x, y) for y in range(foreground.height)
                          for x in range(foreground.width)
                          if (lambda p: p[3] > 128 and p[1] > 120 and p[2] > 65)(foreground.getpixel((x, y)))]
        self.assertGreater(len(highlights), 1000)
        self.assertTrue(all((x-215.5)**2 + (y-215.5)**2 < 144**2 for x, y in highlights))

    def test_substituted_artwork_is_rejected(self):
        other = self.output / "other.png"
        Image.new("RGB", (100, 100), "orange").save(other)
        with self.assertRaisesRegex(ValueError, "approved"):
            launcher_icon.tile_from_source(other)


if __name__ == "__main__":
    unittest.main()
