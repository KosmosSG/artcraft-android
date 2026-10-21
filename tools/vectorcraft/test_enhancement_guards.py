"""Regression guards for the isolated VectorCraft Android enhancement build.

These tests do not require Android SDK, signing secrets, or an APK.
They prevent accidental loss of existing Android bridge/keyboard support and
ensure that the approved icon is selected before a candidate build.
"""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/vectorcraft-baseline.yml"
ICON = ROOT / "assets/branding/vectorcraft/vc-glass-approved.png"


class VectorCraftEnhancementGuards(unittest.TestCase):
    def test_launcher_icon_is_a_full_resolution_png(self):
        with ICON.open("rb") as fh:
            header = fh.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(header[12:16], b"IHDR")
        width, height = struct.unpack(">II", header[16:24])
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 512)

    def test_workflow_builds_using_approved_icon(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("assets/branding/vectorcraft/vc-glass-approved.png", workflow)
        self.assertIn('"-appicon=$ICON"', workflow)
        self.assertIn("0.14.0-android.2", workflow)
        self.assertIn("vectorcraft-photocraft-parity-20261021", workflow)

    def test_existing_android_features_are_preserved(self):
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        java = (
            ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/"
            "VectorCraftActivity.java"
        ).read_text()
        for marker in ("vcRequestOpen", "vcRequestSave", "apply_android_modifiers",
                       "system_fonts::install_font_env"):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)
        for marker in ("vcRequestOpen", "vcRequestSave"):
            with self.subTest(marker=marker):
                self.assertIn(marker, java)

    def test_signing_guards_still_required_and_no_release_published(self):
        workflow = WORKFLOW.read_text()
        for marker in ("VECTORCRAFT_KEYSTORE_BASE64", "VECTORCRAFT_CERT_SHA256",
                       "previous_version_code", "verify_apk.py"):
            with self.subTest(marker=marker):
                self.assertIn(marker, workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
