"""DesignCraft v0.17.2 isolated ARM64 test build source-contract checks.
These do not substitute for compiled-artifact/device regression tests.
"""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DesignCraftV017Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads((ROOT/"configs/upstream/designcraft-v017.json").read_text())
        cls.shell = (ROOT/"lib/build-common.sh").read_text()
        cls.patch = (ROOT/"tools/designcraft/patch_v017_android.py").read_text()
        cls.java = (ROOT/"tools/designcraft/patch_v017_interactions.py").read_text()
        cls.ui = (ROOT/"tools/designcraft/v016_android.rs").read_text()
        cls.fonts = (ROOT/"tools/designcraft/support/font_methods.java").read_text()
        cls.wf = (ROOT/".github/workflows/designcraft-v017-review.yml").read_text()

    def test_pinned_upstream_and_stable_rollback(self):
        self.assertEqual(self.lock["stable_tag"], "v0.17.2")
        self.assertEqual(self.lock["tag_commit"], "16322ad54b3a20b4cd70666be7431086514d0a36")
        self.assertEqual(self.lock["stable_android_release"], "designcraft-v0.12.0-android.9")
        self.assertFalse(self.lock["permanent_signing_authorized"])
        self.assertFalse(self.lock["production_release_authorized"])

    def test_app_scoped_test_and_disposable_key(self):
        self.assertIn('DESIGNCRAFT_V017', self.shell)
        self.assertIn('MODE" != "debug"', self.shell)
        self.assertIn('designcraft-v017.json', self.shell)
        self.assertIn("git clone --depth 1 --branch v0.17.2", self.shell)
        self.assertIn('0.17.2-android.2', self.shell)
        self.assertIn('candidate_version = "0.17.2-android.2"', self.patch)
        self.assertIn('com.artcraft.designcraft.test', self.wf)
        self.assertIn('keys/artcraft-builder.jks', self.shell)
        self.assertNotIn('secrets.', self.wf)
        self.assertNotIn('action-gh-release', self.wf)

    def test_published_font_keyboard_branding_parity_contract(self):
        self.assertIn("count < 5000", self.fonts)
        self.assertIn("4L * 1024 * 1024 * 1024", self.fonts)
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT_TREE", self.fonts)
        self.assertIn("font.reload", self.ui)
        self.assertIn("SHOW_ANDROID_TOOLS", self.ui)
        self.assertIn("select_tool", self.ui)
        self.assertIn("dcDialogHeld.clear();", self.java)
        self.assertIn("return super.dispatchKeyEvent(event);", self.java)
        self.assertIn("approved_branding.check_assets()", self.patch)
        self.assertIn("android.permission.INTERNET", self.patch)

if __name__ == "__main__":
    unittest.main()
