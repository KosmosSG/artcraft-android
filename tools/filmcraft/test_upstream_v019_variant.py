"""Offline version-flavor safety checks; never initiate GitHub Actions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage_upstream_v019_variant as variant

class V019TestFlavor(unittest.TestCase):
    def test_patches_exactly_once(self):
        original = "def build(app, version):\n    code = version_code(version)\n    return code\n"
        updated = variant.patch_text(original)
        self.assertIn('version != "0.19.0"', updated)
        self.assertIn('com.artcraft.filmcraft.test', updated)
        self.assertIn('code = 1900002', updated)
        with self.assertRaises(ValueError):
            variant.patch_text(updated)

    def test_refuses_drift(self):
        with self.assertRaises(ValueError):
            variant.patch_text("code = version_code(version)\n")

    def test_requires_isolated_test_identity(self):
        original = "def build(app, version):\n    code = version_code(version)\n    return code\n"
        updated = variant.patch_text(original)
        self.assertIn('FILMCRAFT_TEST_PACKAGE', updated)
        self.assertIn('FILMCRAFT_ANDROID_VERSION_NAME', updated)
        self.assertIn('FILMCRAFT_EPHEMERAL_VERSION_CODE', updated)

if __name__ == "__main__":
    unittest.main()
