"""Regression guards for PhotoCraft-style VectorCraft Android feedback.

No physical device is available to CI. These static contracts complement
Java compile, Rust ARM64 checks and separate-package tablet verification.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUST = ROOT / "adapters/vectorcraft/src/lib.rs"
ACTIVITY = ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
EXTRAS = ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java"
MENUS = ROOT / "tools/vectorcraft/patch_android_menus.py"


class VectorCraftFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rust = RUST.read_text(encoding="utf-8")
        cls.java = ACTIVITY.read_text(encoding="utf-8")
        cls.extras = EXTRAS.read_text(encoding="utf-8")
        cls.menus = MENUS.read_text(encoding="utf-8")

    def test_native_font_status_matches_photocraft_toast_behavior(self):
        self.assertIn('public void vcShowMessage(String message)', self.java)
        self.assertIn('runOnUiThread(() -> {', self.java)
        self.assertIn('android.widget.Toast.makeText(this, summary,', self.java)
        self.assertIn('if (!isFinishing() && !isDestroyed())', self.java)
        self.assertIn('jni_str!("vcShowMessage")', self.rust)
        self.assertIn('fn native_message(&self, message: &str)', self.rust)
        self.assertIn('self.fonts.notice.take()', self.rust)
        self.assertIn('self.notice = Some(self.shared_status.clone())', self.rust)
        self.assertIn('Shared fonts loaded:', self.extras)
        self.assertIn('Refreshing shared fonts…', self.rust)
        self.assertIn('self.fonts.shared(&self.picks, &self.bridge, true, true)', self.rust)

    def test_quiet_startup_refresh_keeps_current_font_pipeline(self):
        self.assertIn('initial_fonts.shared(&picks, &bridge, true, false);', self.rust)
        self.assertIn('notify_shared_completion: bool', self.rust)
        self.assertIn('if self.notify_shared_completion {', self.rust)
        self.assertIn('if self.fonts.notice.is_some() {', self.rust)
        self.assertIn('self.inner.run("text.rescanFonts"', self.rust)
        self.assertIn('vcRequestFontFolder', self.java)
        self.assertIn('vcRefreshFontFolder', self.java)
        self.assertIn('getPersistedUriPermissions', self.extras)

    def test_update_status_is_visible_in_dock_and_native_notification(self):
        panel = 'egui::Panel::bottom("vectorcraft.android.update_status")'
        editor = 'self.inner.ui(ui);'
        self.assertEqual(self.rust.count(panel), 1)
        self.assertLess(self.rust.index(panel), self.rust.index(editor))
        self.assertNotIn('egui::Window::new("VectorCraft Updates")', self.rust)
        click = self.rust.split('        if check_updates {', 1)[1].split('\n    }\n\n    fn on_exit(', 1)[0]
        for value in (
            'self.updates.open = true;',
            'self.updates.notify_result = true;',
            'self.bridge.native_message(&self.updates.message)',
            'self.bridge.check_for_updates()',
            'ctx.request_repaint();',
            'Already checking GitHub releases',
        ):
            with self.subTest(marker=value):
                self.assertIn(value, click)
        self.assertIn('if self.updates.notify_result && !self.updates.checking {', self.rust)
        self.assertIn('self.updates.notify_result = false;', self.rust)
        self.assertIn('Some("up_to_date")', self.rust)
        self.assertIn('Some("update_available")', self.rust)
        self.assertIn('Some("no_release")', self.rust)
        self.assertIn('Update check timed out.', self.rust)
        self.assertIn('ui.small_button("Dismiss")', self.rust)
        self.assertIn('ui.spinner()', self.rust)
        self.assertIn('ctx.request_repaint_after(', self.rust)

    def test_updates_remain_read_only_and_app_scoped(self):
        self.assertIn('https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v', self.rust)
        self.assertIn('if (!tag.startsWith(TAG_PREFIX)) continue;', self.extras)
        self.assertIn('release.optBoolean("draft")', self.extras)
        self.assertIn('release.optBoolean("prerelease")', self.extras)
        self.assertNotIn('ACTION_INSTALL_PACKAGE', self.extras)
        self.assertNotIn('INSTALL_PACKAGES', self.java)

    def test_existing_font_menu_text_remains_untouched(self):
        for text in (
            'Import Font (.ttf / .otf)…',
            'Select Shared Font Folder…',
            'Refresh Shared Fonts',
            'Check for VectorCraft Updates',
            'Check for Updates at Startup',
        ):
            self.assertIn(text, self.menus)
        self.assertIn('android.vectorcraft.fontRefresh', self.menus)
        self.assertIn('android.vectorcraft.updates', self.menus)


if __name__ == "__main__":
    unittest.main()
