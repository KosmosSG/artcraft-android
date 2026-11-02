"""Regression test for DesignCraft v0.16 pinned Storytold egui panel API."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class StorytoldPanelCompatibility(unittest.TestCase):
    def test_android_panel_uses_pinned_api(self):
        source = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        self.assertIn('egui::Panel::bottom("artcraft-designcraft-android-tools").show(ui, |ui| {', source)
        self.assertNotIn("TopBottomPanel", source)
        self.assertNotIn("egui::BottomPanel", source)

    def test_debug_branch_only(self):
        script = (ROOT / "lib/build-common.sh").read_text()
        self.assertIn('if [[ "$DESIGNCRAFT_V016" == true ]]', script)
        self.assertIn('python3 "$ROOT/tools/designcraft/patch_v016_android.py"', script)

if __name__ == "__main__":
    unittest.main()
