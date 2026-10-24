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

    def test_effectcraft_style_native_update_dialog_replaces_bottom_dock(self):
        self.assertIn('public void vcShowUpdateDialog(String message, String releaseUrl, boolean checking, boolean manualOpen)', self.java)
        self.assertIn('new android.app.AlertDialog.Builder(this)', self.java)
        self.assertIn('.setTitle("VectorCraft Updates")', self.java)
        self.assertIn('.setNegativeButton("Close"', self.java)
        self.assertIn('.setPositiveButton("View Release"', self.java)
        self.assertIn('vcUpdateProgress.setVisibility(checking ? View.VISIBLE : View.GONE)', self.java)
        self.assertIn('vcUpdateDialog.setMessage(message)', self.java)
        self.assertIn('vcUpdateDialogDismissed = true;', self.java)
        self.assertIn('if (manualOpen) vcUpdateDialogDismissed = false;', self.java)
        self.assertIn('if (vcUpdateDialogDismissed) return;', self.java)
        self.assertIn('releaseUrl.matches(', self.java)
        self.assertIn('extras.openRelease(url)', self.java)
        self.assertIn('jni_str!("vcShowUpdateDialog")', self.rust)
        self.assertIn('fn show_update_dialog(&self, message: &str, release_url: &str,', self.rust)
        self.assertNotIn('egui::Panel::bottom("vectorcraft.android.update_status")', self.rust)
        self.assertNotIn('egui::Window::new("VectorCraft Updates")', self.rust)

    def test_manual_check_pops_out_and_completion_updates_same_dialog(self):
        click = self.rust.split('        if check_updates {', 1)[1].split('\\n    }\\n\\n    fn on_exit(', 1)[0]
        for value in (
            'self.updates.notify_result = true;',
            'self.bridge.show_update_dialog(',
            'self.bridge.check_for_updates()',
            'self.updates.checking, true)',
            'ctx.request_repaint();',
            'Already checking GitHub releases',
        ):
            with self.subTest(marker=value):
                self.assertIn(value, click)
        self.assertIn('if self.updates.notify_result && !self.updates.checking {', self.rust)
        self.assertIn('self.updates.notify_result = false;', self.rust)
        self.assertIn('let available_url = if self.updates.message.starts_with("Update available:")', self.rust)
        self.assertIn('self.updates.message, available_url, false, false)', self.rust)
        self.assertIn('Some("up_to_date")', self.rust)
        self.assertIn('Some("update_available")', self.rust)
        self.assertIn('Some("no_release")', self.rust)
        self.assertIn('Update check timed out.', self.rust)
        self.assertIn('ctx.request_repaint_after(', self.rust)
        # Quiet startup check must never open the native dialog.
        self.assertIn('notify_result: bool', self.rust)
        self.assertIn('let mut state = UpdateDialogState::default();', self.rust)

    def test_updates_remain_read_only_and_app_scoped(self):
        self.assertIn('https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v', self.rust)
        self.assertIn('if (!tag.startsWith(TAG_PREFIX)) continue;', self.extras)
        self.assertIn('release.optBoolean("draft")', self.extras)
        self.assertIn('release.optBoolean("prerelease")', self.extras)
        self.assertIn('(!includePreview && release.optBoolean("prerelease"))', self.extras)
        self.assertIn('getBoolean("include_preview_releases", true)', self.extras)
        self.assertIn('Stable + Preview Releases', self.extras)
        self.assertIn('vcShowUpdateChannelSettings', self.java)
        self.assertIn('vcShowUpdateChannelSettings', self.rust)
        self.assertIn('"android.vectorcraft.updateChannel" => 128', self.menus)
        self.assertIn('Update Channel…', self.menus)
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
