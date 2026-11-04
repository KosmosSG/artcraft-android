"""Published DesignCraft .9 feature-parity and v0.17 updater safeguards.

Source contracts do not prove Android runtime behavior; ARM64 compilation and
HONOR MagicPad 4 device verification remain required before accepting any APK.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "652f1475ff02fc7c7dc6b1652f2d36404d931838"


class DesignCraftV017PublishedPreservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.updater = (ROOT / "tools/designcraft/install_v017_updater.py").read_text()
        cls.fonts = (ROOT / "tools/designcraft/support/font_methods.java").read_text()
        cls.policy = (ROOT / "tools/designcraft/support/DesignCraftUpdatePolicy.java").read_text()
        cls.native = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        cls.patch = (ROOT / "tools/designcraft/patch_v017_android.py").read_text()
        cls.interactions = (ROOT / "tools/designcraft/patch_v017_interactions.py").read_text()
        cls.builder = (ROOT / "lib/build-common.sh").read_text()

    def test_protected_published_source_ancestry(self):
        if not (ROOT / ".git").exists():
            self.skipTest("Git metadata unavailable")
        found = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e",
                                BASELINE + "^{commit}"], capture_output=True)
        if found.returncode != 0:
            self.skipTest("Shallow checkout; CI checks full ancestry separately")
        result = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                                 BASELINE, "HEAD"], capture_output=True)
        self.assertEqual(result.returncode, 0, "Wrong published source ancestry")

    def test_published_font_scan_remains_unchanged(self):
        self.assertIn("4L * 1024 * 1024 * 1024", self.fonts)
        self.assertIn("count < 5000", self.fonts)
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT_TREE", self.fonts)
        self.assertIn("getPersistedUriPermissions()", self.fonts)
        self.assertIn("font.reload", self.native)
        self.assertIn("Shared fonts", self.native)
        self.assertIn("TTF/OTF/TTC", self.native)

    def test_existing_update_policy_is_reused_not_replaced(self):
        self.assertIn('update_methods.java', self.updater)
        self.assertIn('DesignCraftUpdatePolicy.java', self.updater)
        self.assertIn('dcCheckUpdates(false)', self.updater)
        self.assertIn('dc_update_action', self.updater)
        self.assertIn('app.artcraftCheckUpdates', self.updater)
        self.assertIn('app.artcraftStartupCheck', self.updater)
        self.assertIn('getPackageName()', (ROOT / "tools/designcraft/support/update_methods.java").read_text())
        self.assertIn('certificate_sha256', self.policy)
        self.assertIn('install_v017_updater import apply', self.patch)

    def test_other_app_and_production_safety(self):
        self.assertIn('src.name != "designcraft"', self.updater)
        self.assertIn('android.name != "designcraft-android"', self.updater)
        self.assertIn('com.artcraft.designcraft.test', self.updater)
        self.assertIn('MODE" != "debug"', self.builder)
        self.assertIn('keys/artcraft-builder.jks', self.builder)

    def test_keyboard_branding_and_input_preservation(self):
        self.assertIn('dcDialogHeld.clear();', self.interactions)
        self.assertIn('super.dispatchKeyEvent(event)', self.interactions)
        self.assertIn('handle_keys', self.native)
        self.assertIn('designcraft.unsaved.dcs', self.native)
        self.assertIn('approved_branding.check_assets()', self.patch)
        self.assertIn('android.permission.INTERNET', self.patch)
        self.assertIn('overlay_winit_android_mouse.py', self.builder)

    def test_fail_closed_updater_patcher(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools/designcraft"))
        from install_v017_updater import once
        self.assertEqual(once("abc", "b", "B", "test"), "aBc")
        with self.assertRaises(ValueError):
            once("abb", "b", "B", "duplicate")
        with self.assertRaises(ValueError):
            once("abc", "z", "Z", "missing")


if __name__ == "__main__":
    unittest.main()
