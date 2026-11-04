"""FilmCraft v0.17 Open/Close/Quit native D/C/S overlay contract."""
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import patch_unsaved_dcs_v017 as dcs

class V017DCSContractTests(unittest.TestCase):
    def test_open_close_quit_routes_and_save_guard(self):
        source = """pub fn show(app: &mut FilmcraftApp, ctx: &egui::Context) {
        match d.command.as_str() {
            "file.closeProject" | "app.quit" | "file.open" => {
                let r = ui.button(tl!("Cancel"));
                let r = ui.button(tl!("Don't Save"));
                let r = ui.add_enabled(can_save, egui::Button::new(tl!("Save")));
                return;
            }
            _ => {}
        }
    if crate::widgets::escape_closes(ctx) {
        action = Some("cancel");
    }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            f = root / "crates/ui-egui/src/panels/clip_dialogs.rs"
            f.parent.mkdir(parents=True)
            f.write_text(source)
            dcs.apply(root)
            out = f.read_text()
            for item in ('(C)', '(D)', '(S)', 'file.open', 'Some(3) if can_save', 'android_unsaved_dcs_active', 'android_capture_unsaved_dcs'):
                self.assertIn(item, out)
            with self.assertRaises(ValueError):
                dcs.apply(root)

if __name__ == "__main__":
    unittest.main()
