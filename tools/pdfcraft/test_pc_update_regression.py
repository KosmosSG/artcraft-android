import base64
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class PdfCraftOwnerUpdateRegression(unittest.TestCase):
    def test_pc_artwork_is_supplied_and_checked(self):
        icon_b64 = (ROOT / "tools/pdfcraft/pc-icon.b64").read_text().strip()
        icon = base64.b64decode(icon_b64, validate=True)
        self.assertEqual(hashlib.sha256(icon).hexdigest(),
            "690439cf43b99f6d5e5f233f2cbb55877cfbe089e823ae2de600035884d5a3f8")
        self.assertEqual(icon[:8], bytes.fromhex("89504e470d0a1a0a"))

    def test_sidebar_scroll_patch_preserves_touch_and_disables_wheel(self):
        patch = (ROOT / "tools/pdfcraft/sidebar_scroll_patch.py").read_text()
        self.assertIn("mouse_wheel: false", patch)
        self.assertIn("DragScroll::OnTouch", patch)
        self.assertIn("scroll_bar: true", patch)
        self.assertIn("upstream sidebar changed", patch)

    def test_update_requires_user_and_existing_signing_identity(self):
        updater = (ROOT / "templates/android/pdfcraft_update_java.txt").read_text()
        self.assertIn("pdfDownloadUpdate(String url, String sha256Digest)", updater)
        self.assertIn("getPackageArchiveInfo", updater)
        self.assertIn("getApkContentsSigners", updater)
        self.assertIn("getLongVersionCode", updater)
        self.assertIn("SessionParams.USER_ACTION_REQUIRED", updater)
        self.assertIn("session.commit(pending.getIntentSender())", updater)
        self.assertIn('session.openWrite("base.apk"', updater)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", updater)
        self.assertNotIn("INSTALL_PACKAGES", updater)
        self.assertIn("DownloadManager", updater)

    def test_compact_updater_separated_from_diagnostics(self):
        rust = (ROOT / "templates/android/pdfcraft_mobile.rs").read_text()
        self.assertIn('egui::Window::new("PDFCraft updates")', rust)
        self.assertIn('egui::Window::new("Android tools")', rust)
        self.assertIn("self.updater_dialog(ctx)", rust)
        self.assertIn('egui::Button::new("Check again")', rust)
        self.assertIn("Check for updates at startup", rust)
        self.assertIn("self.download_ready", rust)

    def test_deckcraft_style_app_updates_submenu_and_startup_toggle(self):
        menu = (ROOT / "tools/pdfcraft/android_tools_menu_patch.py").read_text()
        rust = (ROOT / "templates/android/pdfcraft_mobile.rs").read_text()
        java = (ROOT / "templates/android/pdfcraft_mobile_java.txt").read_text()
        self.assertIn('ui.menu_button("App Updates", |ui|', menu)
        self.assertIn('"✓  Toggle Update Check at Startup"', menu)
        self.assertIn('"Check for Updates…"', menu)
        self.assertNotIn('("Automatic update check…", 5)', menu)
        self.assertIn('let enabled = !self.startup_check;', rust)
        self.assertIn('mobile.read_startup_setting().unwrap_or(true)', rust)
        self.assertIn('getBoolean(PDF_STARTUP_UPDATE_PREF, true)', java)
        self.assertIn('pdfUpdateToast("PDFCraft update checks at startup: "', java)
        self.assertIn('if self.startup_check { self.check_updates(false); }', rust)
        self.assertIn('if self.update_asset_url.is_some() {', rust)
        self.assertIn('pdfInstallDownloadedUpdate', rust)

    def test_updater_does_not_automatic_install(self):
        rust = (ROOT / "templates/android/pdfcraft_mobile.rs").read_text()
        self.assertIn('egui::Button::new("Download APK")', rust)
        self.assertIn('ui.button("Install downloaded APK…")', rust)
        self.assertIn("self.download_ready", rust)
        self.assertIn("pdfInstallDownloadedUpdate", rust)
        self.assertIn("pdfCheckForUpdates", (ROOT / "templates/android/pdfcraft_mobile_java.txt").read_text())

if __name__ == "__main__": unittest.main()
