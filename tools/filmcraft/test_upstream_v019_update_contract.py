"""Static source contract: FilmCraft v0.19 grouped menu and safe APK updater.

These tests run without a device, network, signing key or build. They do NOT
replace the compiled APK audit or MagicPad 4 acceptance.
"""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import header_patch_v019 as header
import verify_android_features_apk_v019 as verify

HERE = Path(__file__).resolve().parent

class UpdaterV019ContractTests(unittest.TestCase):
    def test_gridcraft_style_menu_preserves_approved_header(self):
        header.self_test()
        for label in ("Font Catalog & Diagnostics", "App Updates", "Appearance",
                      "FilmCraft Shortcuts", "About FilmCraft", "Install Verified Download"):
            self.assertIn(label, header.ANDROID_HOME)
        self.assertIn("crate::android_approved_brand::paint", header.ANDROID_HOME)
        self.assertIn('app.settings.appearance', header.ANDROID_HOME)
        self.assertIn("filmcraft.android.menu.action", header.ANDROID_HOME)
        self.assertIn("PointingHand", header.ANDROID_HOME)

    def test_real_jni_updater_download_not_browser_only(self):
        java = (HERE / "FilmCraftActivity.features.v019.java.inc").read_text()
        rust = (HERE / "filmcraft_features_v019.rs").read_text()
        for name in ("fcCheckForUpdates", "fcDownloadVerifiedUpdate",
                     "fcInstallVerifiedDownload", "fcOpenUpdatePage"):
            self.assertIn(name, java)
            self.assertIn(name, rust)
        self.assertIn("android.app.DownloadManager", java)
        self.assertIn("fcExpectedShaFromChecksums", java)
        self.assertIn("fcFileSha256", java)
        self.assertIn("fcVerifyArchive", java)
        self.assertIn("getPackageArchiveInfo", java)
        self.assertIn("canRequestPackageInstalls()", java)
        self.assertIn("com.artcraft.filmcraft.test", java)
        self.assertIn("FilmCraft-v", java)
        self.assertIn("arm64-v8a.apk", java)
        self.assertIn("test_ready", java)
        self.assertIn("APK signing certificate differs", java)
        self.assertIn("fcOfficialAssetUrl", java)

    def test_compiled_contract_requires_permissions_and_jni(self):
        for method in (b"fcDownloadVerifiedUpdate", b"fcInstallVerifiedDownload"):
            self.assertIn(method, verify.JAVA_METHODS)
        self.assertIn(b"fcCheckForUpdates", verify.JAVA_METHODS)
        runtime = (HERE / "runtime_patch_v019.py").read_text()
        self.assertIn("android.permission.REQUEST_INSTALL_PACKAGES", runtime)
        self.assertIn("FilmCraftActivity.features.v019.java.inc", runtime)
        self.assertIn("filmcraft_features_v019.rs", runtime)
        self.assertIn("com.artcraft.filmcraft.test", runtime)

if __name__ == "__main__":
    unittest.main()
