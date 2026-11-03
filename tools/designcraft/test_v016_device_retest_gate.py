"""Device-retest gate for the isolated DesignCraft v0.16 Android.2 candidate."""
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
        self.assertIn("dispatchKeyEvent(KeyEvent event)", stage)
        self.assertIn("dcUnsavedDialog", stage)
        self.assertIn('v016_android::handle_keys(&mut self.inner, ctx, raw, &self.saf_bridge);', stage)
        self.assertIn('candidate_version = "0.16.0-android.3"', launcher)

if __name__ == "__main__":
    unittest.main()
