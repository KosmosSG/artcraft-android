"""Fail-closed static checks for PhotoCraft-style native progress dialog.

The compiled APK verification and physical MagicPad 4 acceptance remain separate gates.
"""
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_android_features_apk_v019 as audit

class PhotoCraftProgressDialogTests(unittest.TestCase):
    def test_native_android_horizontal_progress_and_cancel(self):
        java = (HERE / "FilmCraftActivity.features.v019.photocraft-progress.java.inc").read_text()
        for must in (
            "progressBarStyleHorizontal", "bar.setMax(1000)", "bar.setProgress(clamped * 10)",
            'setTitle("Downloading FilmCraft "', 'setNegativeButton("Cancel"',
            "fcDownloadCancelled.set(true)", "manager.remove(activeId)",
            "fcRejectCancelledDownload()", "fcVerifyDownloadDialog()",
            "fcFinishDownloadDialog(completedMessage, verified)",
            "fcDownloading.compareAndSet(false, true)",
            "fcFileSha256(downloaded)", "fcVerifyArchive(downloaded)",
            "fcExpectedShaFromChecksums(", "fcInstallVerifiedDownload()",
            'if (test) {', "setPositiveButton(\"Install\"",
            "isFinishing()", "isDestroyed()"
        ):
            self.assertIn(must, java, must)

    def test_test_package_does_not_install_published_app(self):
        java = (HERE / "FilmCraftActivity.features.v019.photocraft-progress.java.inc").read_text()
        self.assertIn('if ("com.artcraft.filmcraft.test".equals(getPackageName())) {', java)
        self.assertIn("fcAnswer(\"download\", \"test_ready\"", java)
        self.assertIn('if (!FC_PUBLIC_PACKAGE.equals(getPackageName()))', java)
        self.assertIn("APK signing certificate differs", java)

    def test_rust_does_not_duplicate_toast_each_percentage(self):
        rust = (HERE / "filmcraft_features_v019_photo_progress.rs").read_text()
        self.assertIn('if action == 8 {', rust)
        self.assertIn('kind == "download" && state != "progress"', rust)
        self.assertIn('else if kind == "download" {', rust)
        self.assertIn('ctx.data_mut(|data| data.insert_temp(', rust)

    def test_photo_style_toast_without_floating_startup_window(self):
        rust = (HERE / "filmcraft_features_v019_photo_progress.rs").read_text()
        java = (HERE / "FilmCraftActivity.features.v019.photocraft-progress.java.inc").read_text()
        self.assertIn("startup_check_in_flight: bool", rust)
        self.assertIn("this.startup_check_in_flight = true;", rust)
        self.assertIn('if !startup || state == "available" {', rust)
        self.assertIn('jni_str!("fcShowStatusToast")', rust)
        self.assertIn("android.widget.Toast.makeText(", java)
        self.assertIn("getApplicationContext(), text, android.widget.Toast.LENGTH_SHORT", java)
        self.assertNotIn("filmcraft.android.feedback.overlay", rust)
        self.assertNotIn("Align2::RIGHT_TOP", rust)
        self.assertIn('if ("com.artcraft.filmcraft.test".equals(getPackageName()))', java)
        self.assertIn("fcVerifyDownloadDialog", java)
        self.assertIn("fcInstallVerifiedDownload", java)

    def test_builder_stages_new_files_and_compiled_dex_requires_dialog(self):
        stage = (HERE / "runtime_patch_v019_photo_progress.py").read_text()
        self.assertIn("FilmCraftActivity.features.v019.photocraft-progress.java.inc", stage)
        self.assertIn("filmcraft_features_v019_photo_progress.rs", stage)
        self.assertIn("android.permission.REQUEST_INSTALL_PACKAGES", stage)
        for method in (
            b"fcShowDownloadDialog", b"fcUpdateDownloadDialog",
            b"fcVerifyDownloadDialog", b"fcFinishDownloadDialog",
            b"fcRejectCancelledDownload", b"fcShowStatusToast"):
            self.assertIn(method, audit.JAVA_METHODS)

if __name__ == "__main__":
    unittest.main()
