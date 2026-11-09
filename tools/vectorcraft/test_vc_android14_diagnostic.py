"""Source-only checks for the one-time VectorCraft Android.14 diagnostic build."""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT/"tools/vectorcraft"

class DiagnosticSessionGuards(unittest.TestCase):
    def test_diagnostic_panel_is_opt_in_and_copied_only_on_button(self):
        src=(TOOLS/"patch_android14_diagnostic_session.py").read_text()
        for marker in (
            "if vc_diag_start", "if vc_diag_stop", "if vc_diag_copy",
            'ui.button("Copy Report")', 'ui.button("Start / Reset")',
            "self.bridge.copy_diagnostic_report(&report)",
            "self.vc_diag_recording", "vcDiagStartupStage",
            "vcDiagPixelsChecked", "vcDiagnosticSnapshot",
        ):
            self.assertIn(marker, src)
        self.assertIn("if self.vc_diag_recording", src)
        self.assertIn("while self.vc_diag_history.len() > 60", src)
        self.assertIn("if !editing && !composing && !field_focused", src)

    def test_no_document_or_keystroke_recording_or_automatic_sharing(self):
        src=(TOOLS/"patch_android14_diagnostic_session.py").read_text()
        self.assertIn("No typed text, document content, filenames", src)
        self.assertIn("vcDiagLastShortcut = (hardwareShortcutMode == 0", src)
        self.assertIn('if (report == null || report.length() > 12000) return;', src)
        self.assertNotIn("ACTION_SEND", src)
        self.assertNotIn("HTTP", src)
        self.assertNotIn("imeEvents.toString()", src)
        self.assertNotIn("keyEvent.getCharacters()", src)
        self.assertNotIn("document.serialize", src)

    def test_startup_marker_survives_quit_without_hotpath_disk_access(self):
        src=(TOOLS/"patch_android14_diagnostic_session.py").read_text()
        self.assertIn("startup_pending_first_frame", src)
        self.assertIn("editor_first_frame_verified", src)
        self.assertIn("prior_process_stage=", src)
        self.assertIn("No preference write or disk read on hot startup/pixel-copy paths", src)

    def test_guards_and_arm64_test_package_only(self):
        flow=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.23", flow)
        self.assertIn("VERSION_CODE: '16783383'", flow)
        self.assertIn("patch_android14_diagnostic_session.py", flow)
        self.assertIn("com.artcraft.vectorcraft.test", flow)
        self.assertIn("Delete disposable builder signing materials", flow)
        self.assertNotIn("gh release create", flow)

if __name__ == "__main__":
    unittest.main()
