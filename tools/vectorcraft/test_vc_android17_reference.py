"""Android.17 reference-adoption regression checks — owner features protected."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class ReferenceStartupAndInputTests(unittest.TestCase):
    def test_no_native_pixelcopy_startup_gate_or_custom_cover(self):
        s=(TOOLS/"patch_android17_reference_adoption.py").read_text()
        self.assertIn('splash.setKeepOnScreenCondition(() -> startupCover == null',s)
        self.assertIn('showStartupCover();',s)
        self.assertIn('reference_direct_native_surface',s)
        self.assertIn('reference_native_ui_ready',s)
        self.assertIn('nativeEditorReady = true;',s)

    def test_modal_wake_and_focus_recovery(self):
        s=(TOOLS/"patch_android17_reference_adoption.py").read_text()
        for token in (
            "vcWakeNativeLoop",
            "dispatchKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_UNKNOWN))",
            "postInvalidateOnAnimation()",
            "self.bridge.wake_native_loop()",
            "if (hardwareShortcutMode != mode) physicalShortcutKeys.clear();",
            "surface.requestFocus();",
            "if (mode == 1 && !imeWanted)",
        ):
            self.assertIn(token,s)
        self.assertIn("self.vc_modal_followup_repaints = 8;",s)
        self.assertNotIn("android.os.Process.killProcess",s)

    def test_modifiers_preserve_both_reference_physical_state_and_input_flags(self):
        s=(TOOLS/"patch_android17_reference_adoption.py").read_text()
        self.assertIn("from_hardware = state.modifiers()",s)
        self.assertIn("incoming_nonempty = incoming.ctrl",s)
        self.assertIn("egui::Key::ControlLeft",s)
        self.assertIn("egui::Event::WindowFocused(false)",s)
        self.assertIn("egui::Event::Text(_) if state.modifiers().ctrl",s)

    def test_version_and_no_release(self):
        flow=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.22",flow)
        self.assertIn("VERSION_CODE: '16783382'",flow)
        self.assertIn("patch_android17_reference_adoption.py",flow)
        self.assertIn("com.artcraft.vectorcraft.test",flow)
        self.assertIn("Delete disposable builder signing materials",flow)
        self.assertNotIn("gh release create",flow)

if __name__=="__main__":
    unittest.main()
