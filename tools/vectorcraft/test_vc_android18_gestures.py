"""VectorCraft Android.18 device regression guards.

No permanent signing/publish, no owner feature removal. Check generated
Android, modal-only D/S/C, V/C upstream tool letters and native pinch routing.
"""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android18Guards(unittest.TestCase):
    def test_splash_and_modal_focus(self):
        p=(TOOLS/"patch_android18_modal_and_gestures.py").read_text()
        for token in [
            'splash.setKeepOnScreenCondition(() -> !nativeEditorReady)',
            'native_editor_visible',
            'mode == 2 && previousMode != 2',
            'imeView.clearFocus();',
            'nativeSurface.requestFocus();',
            'vcWakeNativeLoop();',
        ]: self.assertIn(token,p)
        self.assertNotIn("killProcess(",p)
    def test_native_tool_letters_and_upstream_canvas_gesture(self):
        p=(TOOLS/"patch_android18_modal_and_gestures.py").read_text()
        for token in [
            'KeyEvent.KEYCODE_A && key <= KeyEvent.KEYCODE_Z',
            '(31, 1) => Some(egui::Key::C)',
            '(50, 1) => Some(egui::Key::V)',
            'app.session.prefs.touch_gestures = true;',
            'source/vectorcraft/crates/ui-egui/src/canvas/input.rs',
            'touch_center.is_some()',
            'resp.hovered() || gesture_on_canvas',
            'touch_center.or(hover)',
        ]: self.assertIn(token,p)
        self.assertNotIn('delete_file',p)
    def test_test_only_release_rules(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.20",w)
        self.assertIn("VERSION_CODE: '16783380'",w)
        self.assertIn("patch_android18_modal_and_gestures.py",w)
        self.assertIn("com.artcraft.vectorcraft.test",w)
        self.assertIn("Delete disposable builder signing materials",w)
        self.assertNotIn("gh release create",w)

if __name__=="__main__":
    unittest.main()
