"""VectorCraft Android.16 UI-frame modal/action and SAF diagnostics gates."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android16ModalFrameTests(unittest.TestCase):
    def test_deferred_modal_actions_are_scoped_and_bounded(self):
        s=(TOOLS/"patch_android16_modal_frame.py").read_text()
        for item in (
            "vc_modal_pending_action",
            "vc_modal_followup_repaints",
            "Some((key, source))",
            "self.vc_modal_pending_action.take()",
            "self.inner.android_owner_unsaved_key(key)",
            "self.vc_modal_followup_repaints = 8",
            "ctx.request_repaint_after(std::time::Duration::from_millis(16))",
            "egui::Key::D | egui::Key::S",
            'dialog_after={after_dialog} phase=logic',
        ):
            self.assertIn(item,s)
        self.assertNotIn("finishAndRemoveTask()",s)
        self.assertNotIn("permanent",s.lower())

    def test_save_picker_has_private_stage_only(self):
        s=(TOOLS/"patch_android16_modal_frame.py").read_text()
        for stage in ("queued_to_ui_thread","launching","launch_requested",
                      "launch_failed","result_ok","cancelled","answer_queued",
                      "frame_probe_stage","waiting_surface","pixelcopy_requested"):
            self.assertIn(stage,s)
        self.assertNotIn('vcDiagSavePickerStage = suggestedName',s)
        self.assertNotIn('vcDiagSavePickerStage = uri',s)
        self.assertNotIn('vcDiagSavePickerStage = name',s)

    def test_temp_signed_test_package_and_no_publish(self):
        flow=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("0.21.0-android.17",flow)
        self.assertIn("16783377",flow)
        self.assertIn("patch_android16_modal_frame.py",flow)
        self.assertIn("com.artcraft.vectorcraft.test",flow)
        self.assertIn("Delete disposable builder signing materials",flow)
        self.assertNotIn("gh release create",flow)

if __name__ == "__main__":
    unittest.main()
