"""Source regression gates for visible font import and LightCraft-style update UI.

Actual Android compilation, original signer check and real-APK contents are
verified separately in the private release-preview workflow.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class FeedbackUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        cls.java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        cls.activity=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        cls.about=(ROOT/"tools/vectorcraft/patch_android_about_updates.py").read_text()
        cls.font=(ROOT/"tools/vectorcraft/test_keyboard_production_upgrade.py").read_text()

    def test_visible_font_import_feedback_for_success_duplicate_cancel_error(self):
        s=self.shell
        for marker in ('self.font_feedback_open = true;', 'egui::Window::new("VectorCraft Fonts")',
            'ui.heading("Font Import")', 'self.fonts.import_status', 'self.fonts.shared_status',
            'self.fonts.pending_import.is_some()', 'self.fonts.pending_shared.is_some()',
            'if ui.button("Close").clicked()', 'FontUiState', 'fonts.consume(id, &value)'):
            with self.subTest(marker=marker): self.assertIn(marker,s)
        for marker in ('"cancel", "Selection cancelled"', '"ok", "This font is already available"',
                       '"ok", "Font imported to private Fonts/Imported folder"',
                       '"error", error.toString()'):
            with self.subTest(marker=marker): self.assertIn(marker,self.java)

    def test_updater_native_about_tab_matches_lightcraft_ui_contract(self):
        for marker in ('ORIGINAL_TABS', 'PATCHED_MATCH', 'ui.heading("VectorCraft Updates")',
            'Installed Version:', 'Stable Releases Only', 'Stable + Preview Releases',
            'Check for updates at startup', 'Open GitHub Release',
            'Check for Updates', 'Preview releases may be untested'):
            with self.subTest(marker=marker): self.assertIn(marker,self.about)
        self.assertIn('self.inner.ui.about = true;',self.shell)
        self.assertIn('egui::Id::new("about_tab"), 3u8',self.shell)
        self.assertNotIn('egui::Panel::bottom("vectorcraft.android.update_status")',self.shell)
        for marker in ('artcraft.vectorcraft.update_status',
           'artcraft.vectorcraft.check_updates_requested',
           'artcraft.vectorcraft.preview_changed',
           'artcraft.vectorcraft.startup_changed',
           'artcraft.vectorcraft.open_release_requested'):
            self.assertIn(marker,self.shell)
            self.assertIn(marker,self.about)

    def test_channel_and_exact_release_filtering_preserve_original_signer(self):
        for marker in ('vcGetIncludePreviewUpdates','vcSetIncludePreviewUpdates'):
            self.assertIn(marker,self.shell)
            self.assertIn(marker,self.activity)
        for marker in ('includePreviewUpdates()', 'setIncludePreviewUpdates(boolean enabled)',
                       'getBoolean("include_preview_releases", true)',
                       'putBoolean("include_preview_releases", enabled)',
                       '(!includePreview && release.optBoolean("prerelease"))',
                       '("VectorCraft-v" + version + "-arm64-v8a.apk").equals(filename)',
                       '"uploaded".equals(asset.optString("state", ""))',
                       'asset.optLong("size", 0L) > 0'):
            self.assertIn(marker,self.java)
        self.assertIn('com.artcraft.vectorcraft',self.activity)
        self.assertNotIn('keyboardtest',self.shell)
        self.assertIn('CanvasHardwareCommand::PreserveContextBar',self.shell)
        self.assertNotIn('self.inner.ui.task_bar = false;',self.shell)

if __name__=="__main__":
    unittest.main()
