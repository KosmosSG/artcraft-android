"""EffectCraft logo-menu and folder-picker return source regression tests."""
import tempfile
import unittest
from pathlib import Path
from menu_corner import ANCHOR, patch_header
ROOT = Path(__file__).parent

class MenuAndPickerTest(unittest.TestCase):
    def test_existing_brand_icon_menu_and_about(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "crates/ui-egui/src/header.rs"
            path.parent.mkdir(parents=True)
            path.write_text("fn brand() {\n" + ANCHOR + "\n}")
            patch_header(root)
            result = path.read_text()
            self.assertEqual(result.count("egui::Popup::menu(&bresp)"), 1)
            for title in ("Import Fonts", "Select Font Folder", "Refresh Fonts Folder",
                          "Check for Updates", "Startup Update Check", "About EffectCraft"):
                self.assertIn(title, result)
            self.assertIn('#[cfg(not(target_os = "android"))]', result)
            self.assertIn('egui::ScrollArea::vertical()', result)
            self.assertIn('.max_height(236.0)', result)
            self.assertIn('ui.set_width(268.0)', result)
            self.assertIn('ui.set_max_width(278.0)', result)
            self.assertNotIn('.auto_shrink([false, true])', result)
            # Android.7 removes headings but retains the actions below them.
            self.assertNotIn('ui.label(egui::RichText::new("Fonts").strong())', result)
            self.assertNotIn('ui.label(egui::RichText::new("Updates").strong())', result)
            self.assertIn('ui.menu_button("Appearance"', result)
            for mode in ('("System", "auto")', '("Light", "light")', '("Dark", "dark")'):
                self.assertIn(mode, result)
            self.assertIn('app.set_pref(', result)
            self.assertIn('"appearance.appearanceMode"', result)
            self.assertIn('app.apply_prefs(ui.ctx())', result)
            self.assertIn('ui.selectable_label(current == value, label)', result)
            with self.assertRaisesRegex(RuntimeError, "STOP"):
                patch_header(root)

    def test_unexpected_upstream_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "crates/ui-egui/src/header.rs"
            path.parent.mkdir(parents=True)
            path.write_text("changed upstream")
            with self.assertRaisesRegex(RuntimeError, "STOP"):
                patch_header(Path(d))

    def test_no_old_window_help_duplicates(self):
        script = (ROOT / "integrate_updater.py").read_text()
        self.assertIn('patch_header(root / "source/effectcraft")', script)
        self.assertNotIn('if label == "Window"', script)
        self.assertNotIn('if label == "Help"', script)

    def test_return_to_editor_only_if_coming_from_editor(self):
        java=(ROOT / "FontsBridge.java.inc").read_text()
        rust=(ROOT / "android_updater.rs").read_text()
        self.assertIn('ecFontPaths.offer("picker-return|")', java)
        self.assertIn('path == "picker-return|"', rust)
        self.assertIn("self.restore_editor_after_picker = !*start_screen;", rust)
        self.assertIn("if self.restore_editor_after_picker", rust)
        self.assertIn("*start_screen = false;", rust)
        self.assertIn("self.updates.ui(ui.ctx(), &mut self.inner.ui.start_screen)", (ROOT / "integrate_updater.py").read_text())

if __name__ == "__main__":
    unittest.main()
