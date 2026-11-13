"""Cheap WordCraft-only Stylus Wheel regression gate; no Android SDK needed."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "stylus_wheel.rs").read_text()
NATIVE = (ROOT / "wordcraft_android.rs").read_text()
JAVA = (ROOT / "WordCraftExtension.java.inc").read_text()
BUILDER = (ROOT / "patch_builder.py").read_text()
MENU = (ROOT / "ribbon_android.rs.inc").read_text()


class BlueWheelTests(unittest.TestCase):
    def test_isolated_and_user_approved_style(self):
        for text in ("WC_BLUE_STYLUS_WHEEL_V1", "Wc", "CYAN", "HUB",
                     "Color32::from_rgb(10, 54, 116)", "Color32::from_rgb(62, 195, 255)",
                     "Color32::from_rgba_unmultiplied(65, 68, 73", "Color32::from_black_alpha",
                     "egui::Shape::convex_polygon"):
            self.assertIn(text, SRC)

    def test_full_size_preview_and_customization(self):
        for text in ("170.0..=380.0", "0.25..=1.0", "Live preview", "Reset to default",
                     "Edit shortcuts", "self.paint(ui.painter(), rect.center(), self.size, self.opacity",
                     "Wheel size", "Wheel opacity", "config_json"):
            self.assertIn(text, SRC)

    def test_only_known_edit_and_draw_commands(self):
        expected = ("draw.pen", "draw.eraser", "draw.highlighter", "draw.select",
                    "edit.copy", "edit.paste", "edit.undo", "edit.redo",
                    "format.bold", "format.italic", "file.save", "draw.pencil", "draw.lasso")
        self.assertEqual(len(expected), 13)
        for command in expected:
            self.assertIn('"' + command + '"', SRC)
        self.assertIn("DEFAULT: [usize; 8]", SRC)

    def test_raw_hover_and_ink_never_reach_canvas(self):
        for text in ("filter_input", "TouchPhase::Start", "TouchPhase::End",
                     "Event::PointerGone", "self.owns", "raw.events = events",
                     "MouseWheel", "WC_WHEEL_HOVER_ISOLATION_V1"):
            self.assertIn(text, SRC)
        self.assertIn("self.wheel.owns(egui::pos2(p[0], p[1]), screen)", NATIVE)
        self.assertIn("self.wheel.filter_input(raw, screen);", NATIVE)
        self.assertIn("wc_wheel_input", BUILDER)
        self.assertIn("self.wc.isolate_wheel_input(ctx, raw)", BUILDER)
        # Inject before WordApp's own clipboard/shortcut/canvas event handling.
        injected = next(line for line in BUILDER.splitlines() if "{wc_wheel_input}" in line)
        self.assertLess(injected.index("{wc_wheel_input}"), injected.index("self.handle_clipboard_shortcuts(raw)"))

    def test_settings_java_private_and_menu(self):
        for text in ("wcGetStylusWheelPrefs", "wcSetStylusWheelPrefs",
                     'getSharedPreferences("wordcraft_android_wheel", MODE_PRIVATE)'):
            self.assertIn(text, JAVA)
        for text in ("wheel_customize", "wheel_on", "wheel_off", "save_wheel",
                     "self.wheel.show(ctx)", "stylus_wheel::CHOICES"):
            self.assertIn(text, NATIVE)
        self.assertIn("Show Stylus Wheel", MENU)
        self.assertIn("Customize Stylus Wheel", MENU)
        self.assertIn("wc_menu_wheel_visible", MENU)
        self.assertIn("mod stylus_wheel;", NATIVE)
        self.assertIn("stylus_wheel.rs", BUILDER)

    def test_no_production_or_cross_app_mutation(self):
        self.assertNotIn("MANAGE_EXTERNAL_STORAGE", SRC)
        self.assertNotIn("keystore", SRC.lower())
        self.assertNotIn("publish", SRC.lower())
        self.assertTrue((ROOT / "patch_touch_guard.py").is_file())


if __name__ == "__main__":
    unittest.main()
