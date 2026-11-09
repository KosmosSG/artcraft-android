"""VectorCraft Android.15 modal-only keyboard regression guards."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android15ModalGuards(unittest.TestCase):
    def test_native_or_ime_fallback_routes_d_s_c_only_in_modal(self):
        s=(TOOLS/"patch_android15_modal_keys.py").read_text()
        for m in (
            "hardwareShortcutMode != 2 || imeWanted",
            "vcOfferModalShortcut(event.getKeyCode(), event.getDownTime()",
            "vcOfferModalShortcut(keyCode, event.getDownTime()",
            "vcOfferModalCommit(text)",
            "event.isShiftPressed(), event.isAltPressed()",
            "egui::Event::Text(text) if text.len() == 1",
            "self.inner.android_owner_unsaved_key(key)",
            'dialog_after={after_dialog}',
        ):
            self.assertIn(m,s)
        self.assertIn('let before_docs = self.inner.session.documents().len()',s)
        self.assertIn('self.vc_diag_last_modal_action',s)

    def test_scoped_keys_do_not_break_typing_or_cancel(self):
        s=(TOOLS/"patch_android15_modal_keys.py").read_text()
        self.assertIn("keyCode == KeyEvent.KEYCODE_C",s)
        self.assertIn("egui::Key::C",s)
        self.assertIn('self.inner.ui.dialog.as_ref().is_some_and(|d| d.kind == "saveChanges")', (TOOLS/"patch_android13_recovery.py").read_text())
        self.assertIn('vcLastModalKeyDownTime',s)
        self.assertNotIn("finishAndRemoveTask()",s)
        self.assertNotIn('findNativeSurface(',s)
        self.assertNotIn('screenCapture',s)

    def test_test_only_apk_is_separate_and_not_published(self):
        flow=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.21",flow)
        self.assertIn("VERSION_CODE: '16783381'",flow)
        self.assertIn("patch_android15_modal_keys.py",flow)
        self.assertIn('com.artcraft.vectorcraft.test',flow)
        self.assertIn("Delete disposable builder signing materials",flow)
        self.assertNotIn("gh release create",flow)

if __name__ == "__main__":
    unittest.main()
