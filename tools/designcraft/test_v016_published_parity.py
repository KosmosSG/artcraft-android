"""Regressions from the user's published DesignCraft android.9 device baseline.

The v0.16 Android review does not change the public build or its key.
These checks protect source-level parity; real hardware testing remains required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DesignCraftPublishedFeatureParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        cls.java = (ROOT / "tools/designcraft/patch_v016_interactions.py").read_text()
        cls.fonts = (ROOT / "tools/designcraft/support/font_methods.java").read_text()
        cls.base = (ROOT / "tools/designcraft/patch_v016_android.py").read_text()
        cls.builder = (ROOT / "lib/build-common.sh").read_text()

    def test_existing_font_catalog_and_saf_limits_preserved(self):
        self.assertIn("count < 5000", self.fonts)
        self.assertIn("4L * 1024 * 1024 * 1024", self.fonts)
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT_TREE", self.fonts)
        self.assertIn("getPersistedUriPermissions()", self.fonts)
        self.assertIn("pending.addLast(documentId)", self.fonts)
        self.assertIn("font.reload", self.ui)
        self.assertIn("TTF/OTF/TTC", self.ui)

    def test_toolbar_is_recoverable_after_hiding(self):
        self.assertIn('take_android_tools_toggle()', self.ui)
        self.assertIn('SHOW_ANDROID_TOOLS', self.ui)
        self.assertIn('small_button("Hide Tools")', self.ui)
        self.assertIn('"ui:app.artcraftToggleAndroidTools"', self.java)
        self.assertIn("Show / Hide Android Tools", self.java)

    def test_font_scan_progress_and_outcomes_are_visible(self):
        self.assertIn("Refreshing shared fonts…", self.ui)
        self.assertIn("shared-font scan is already running", self.ui)
        self.assertIn("SHARED_SCAN_PENDING.store(false", self.ui)
        self.assertIn("USER_MESSAGE.lock()", self.ui)
        self.assertIn("font catalog refreshed", self.ui)
        self.assertIn("Shared fonts: {e}", self.ui)

    def test_modal_keys_and_tool_keys_do_not_break_text_editing(self):
        self.assertIn("dcDialogHeld.clear();", self.java)
        self.assertIn("super.dispatchKeyEvent(event)", self.java)
        self.assertIn('designcraft.unsaved.dcs', self.ui)
        self.assertIn('forward_ui_shortcuts(ui, app)', self.ui)
        self.assertIn('app.session.wants_text()', self.ui)
        self.assertIn('ctx.text_edit_focused()', self.ui)
        self.assertIn('app.select_tool(tool)', self.ui)
        self.assertIn('app.select_tool("selection")', self.ui)

    def test_review_isolated_from_published_release(self):
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true ]]', self.builder)
        self.assertIn('candidate_version = "0.16.0-android.3"', self.base)
        self.assertIn('approved_branding.check_assets()', self.base)
        self.assertIn('android.permission.INTERNET', self.base)
        self.assertIn("0.16.0-android.3", self.builder)
        workflow = (ROOT / ".github/workflows/designcraft-v016-review.yml").read_text()
        self.assertIn("NOT a release", workflow)
        self.assertNotIn("action-gh-release", workflow)
        self.assertNotIn("secrets.", workflow)

if __name__ == "__main__":
    unittest.main()
