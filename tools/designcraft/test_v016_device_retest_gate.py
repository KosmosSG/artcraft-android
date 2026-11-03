"""Device-retest gate for the isolated DesignCraft v0.16 Android.4 candidate."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DeviceRetestGate(unittest.TestCase):
    def test_android4_has_shared_fonts_and_keyboard_bridge(self):
        ui = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        stage = (ROOT / "tools/designcraft/patch_v016_interactions.py").read_text()
        launcher = (ROOT / "tools/designcraft/patch_v016_android.py").read_text()
        self.assertIn("Select Shared Font Folder", ui)
        self.assertIn("Refresh Shared Fonts", ui)
        self.assertIn("SHARED_SCAN_PENDING", ui)
        self.assertIn("SHOW_ANDROID_TOOLS", ui)
        self.assertIn("take_android_tools_toggle", ui)
        self.assertIn("request_repaint_after", ui)
        self.assertIn("take_android_tools_toggle", stage)
        self.assertIn("Shared font folder selection cancelled", stage)
        self.assertIn("return super.dispatchKeyEvent(event);", stage)
        self.assertIn('egui::Key::T', ui)
        self.assertIn('egui::Key::V', ui)
        self.assertIn('egui::Key::Escape', ui)
        self.assertIn("dispatchKeyEvent(KeyEvent event)", stage)
        self.assertIn("dcUnsavedDialog", stage)
        self.assertIn("dcTakeToolAction", stage)
        self.assertIn("dc_tool_action(&self)", stage)
        self.assertIn("dcDialogAction.compareAndSet(0, action)", stage)
        self.assertIn("if (dcDialogHeld.contains(code))", stage)
        self.assertIn("Consume repeats as well as the matching key release", stage)
        self.assertIn("return true;", stage)
        self.assertIn("request_repaint_after(std::time::Duration::from_millis(80))", ui)
        self.assertIn("bridge.dc_tool_action()", ui)
        self.assertIn('if escape && !dialog && app.ui.palette.is_none()', ui)
        self.assertNotIn("!imeWanted && event.hasNoModifiers()", stage)
        self.assertIn('v016_android::handle_keys(&mut self.inner, ctx, raw, &self.saf_bridge);', stage)
        self.assertIn('candidate_version = "0.16.0-android.4"', launcher)
        shell = (ROOT / "lib/build-common.sh").read_text()
        self.assertIn("renderer: eframe::Renderer::Wgpu,", shell)
        self.assertIn("cc.wgpu_render_state", shell)
        self.assertIn("state.adapter.get_info()", shell)
        self.assertIn("v016_android::set_gpu_adapter", shell)
        self.assertIn("GPU_STATUS", ui)

if __name__ == "__main__":
    unittest.main()
