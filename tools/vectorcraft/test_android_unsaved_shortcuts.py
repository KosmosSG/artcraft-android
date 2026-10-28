"""Structural regression guards for VectorCraft's staged Save Changes shortcuts."""
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

class UnsavedKeyboardPatchTest(unittest.TestCase):
    def test_patch_scoped_to_unsaved_dialog(self):
        patch = (HERE / "patch_android_unsaved_shortcuts.py").read_text()
        self.assertIn("d.kind == crate::unsaved::KIND", patch)
        self.assertIn("A stale focused Type editor must NOT disable the modal hotkeys.", patch)
        self.assertIn("Popup::is_any_open(ctx)", patch)
        for key in ("C", "D", "S", "Escape"):
            self.assertIn("egui::Key::" + key, patch)
        self.assertIn("consume_key(egui::Modifiers::NONE, key)", patch)
        self.assertIn("discard = true", patch)
        self.assertIn("cancel = true", patch)
        self.assertIn("ok_enabled && pressed(egui::Key::S)", patch)
        self.assertIn("crate::unsaved::confirm(app)", patch)
        for hint in ("Save (S)", "Cancel (C)", "Save (D)"):
            self.assertIn(hint, patch)

if __name__ == "__main__":
    unittest.main()
