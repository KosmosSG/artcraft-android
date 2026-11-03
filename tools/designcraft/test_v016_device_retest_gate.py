"""Device-retest gate for the isolated DesignCraft v0.16 Android.3 candidate."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class DeviceRetestGate(unittest.TestCase):
    def test_android3_has_shared_fonts_and_keyboard_bridge(self):
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
        self.assertIn('v016_android::handle_keys(&mut self.inner, ctx, raw, &self.saf_bridge);', stage)
        self.assertIn('candidate_version = "0.16.0-android.3"', launcher)

if __name__ == "__main__":
    unittest.main()
