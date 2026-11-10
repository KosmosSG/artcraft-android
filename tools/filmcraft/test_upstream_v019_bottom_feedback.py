"""FilmCraft v0.19 PhotoCraft-style bottom pill regression contract.

Runs before CI ARM64 build; leaves published baseline and production signing alone.
"""
import unittest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import verify_android_features_apk_v019 as compiled

RUST = HERE / "filmcraft_features_v019_bottom_feedback.rs"
JAVA = HERE / "FilmCraftActivity.features.v019.bottom-feedback.java.inc"
RUNTIME = HERE / "runtime_patch_v019_bottom_feedback.py"


class PhotoCraftBottomFeedbackTests(unittest.TestCase):
    def test_photo_style_bottom_center_pill(self):
        s = RUST.read_text()
        self.assertIn("egui::Align2::CENTER_BOTTOM", s)
        self.assertIn('filmcraft.android.feedback.bottom_pill', s)
        self.assertIn('egui::vec2(0.0, -58.0)', s)
        self.assertIn('egui::RichText::new("Fc")', s)
        self.assertIn("ui.horizontal_wrapped(|ui|", s)
        self.assertIn("corner_radius(22.0)", s)
        self.assertIn("interactable(false)", s)
        self.assertNotIn("egui::Align2::RIGHT_TOP", s)
        self.assertNotIn('filmcraft.android.feedback.overlay', s)

    def test_status_events_use_one_center_pill_without_progress_toasts(self):
        s = RUST.read_text()
        self.assertIn('kind == "download" && state != "progress"', s)
        self.assertIn('action == 8 && self.pending_download', s)
        self.assertIn("Self::native_menu_status(ctx, &self.update_status)", s)
        self.assertIn("Self::native_menu_status(ctx, &self.font_status)", s)
        self.assertIn('ctx.data_mut(|data| data.remove::<(String, f64)>(key))', s)
        self.assertNotIn('data.insert_temp(egui::Id::new("filmcraft.android.menu.status")', s)
        self.assertIn('self.show_feedback(ui.ctx())', s)

    def test_download_dialog_stays_but_test_result_has_no_second_modal(self):
        s = JAVA.read_text()
        self.assertIn('fcShowDownloadDialog', s)
        self.assertIn('fcUpdateDownloadDialog', s)
        self.assertIn('fcFinishDownloadDialog', s)
        self.assertIn('fcRejectCancelledDownload', s)
        self.assertIn('fcExpectedShaFromChecksums(', s)
        self.assertIn('fcFileSha256(downloaded)', s)
        self.assertIn('fcVerifyArchive(downloaded)', s)
        self.assertIn('manager.remove(activeId)', s)
        self.assertIn('boolean test = "com.artcraft.filmcraft.test".equals(getPackageName())', s)
        self.assertIn("Result is already routed to the PhotoCraft-style bottom", s)
        self.assertIn('if (test) {', s)
        self.assertIn('next.setPositiveButton("Install"', s)
        self.assertIn('fcAnswer("download", "test_ready"', s)

    def test_disposable_android_builder_stages_exact_new_overlay(self):
        s = RUNTIME.read_text()
        self.assertIn(JAVA.name, s)
        self.assertIn(RUST.name, s)
        self.assertIn("com.artcraft.filmcraft.test", s)
        self.assertIn("android.permission.REQUEST_INSTALL_PACKAGES", s)
        for method in (
            b"fcCheckForUpdates", b"fcDownloadVerifiedUpdate",
            b"fcInstallVerifiedDownload",
            b"fcShowDownloadDialog", b"fcFinishDownloadDialog",
        ):
            self.assertIn(method, compiled.JAVA_METHODS)


if __name__ == "__main__":
    unittest.main()
