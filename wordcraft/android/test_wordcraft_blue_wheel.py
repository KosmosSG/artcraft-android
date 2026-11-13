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
                     "Color32::from_rgb(14, 82, 165)", "Color32::from_rgb(122, 216, 252)",
                     "SEGMENT_GREY_LIGHT", "SEGMENT_GREY_DARK", "Color32::from_black_alpha",
                     "egui::Shape::convex_polygon"):
            self.assertIn(text, SRC)

    def test_android9_defaults_greys_and_launcher_logo(self):
        # New installs and Reset must be 200pt / 100% opacity, without
        # changing previously saved customization preferences.
        self.assertIn("WC_ANDROID9_APPROVED_DEFAULTS_AND_GREY_SEGMENTS_V1", SRC)
        self.assertIn("const DEFAULT_WHEEL_SIZE: f32 = 200.0;", SRC)
        self.assertIn("const DEFAULT_WHEEL_OPACITY: f32 = 1.0;", SRC)
        self.assertIn("size: DEFAULT_WHEEL_SIZE,", SRC)
        self.assertIn("opacity: DEFAULT_WHEEL_OPACITY,", SRC)
        self.assertIn("self.size = DEFAULT_WHEEL_SIZE;", SRC)
        self.assertIn("self.opacity = DEFAULT_WHEEL_OPACITY;", SRC)
        self.assertIn('value["size"].as_f64()', SRC)
        self.assertIn('value["opacity"].as_f64()', SRC)
        # As in PhotoCraft, alternating slot tones should be subtle.
        self.assertIn("SEGMENT_GREY_LIGHT: Color32 = Color32::from_rgb(68, 70, 75)", SRC)
        self.assertIn("SEGMENT_GREY_DARK: Color32 = Color32::from_rgb(51, 54, 59)", SRC)
        self.assertIn("if i % 2 == 0 { SEGMENT_GREY_LIGHT } else { SEGMENT_GREY_DARK }", SRC)
        self.assertIn("normal.r(), normal.g(), normal.b()", SRC)
        self.assertIn("Color32::from_rgba_unmultiplied(9, 113, 212", SRC)
        # Preserve exact Wc launcher glyph bitmap; reduce both dimensions
        # by ten percent, move logo lower, leave label and hub alone.
        self.assertIn("WC_ANDROID9_APPROVED_WC_LOGO_V1", SRC)
        self.assertIn("let logo = Self::wc_mark(ctx);", SRC)
        self.assertIn("size * 0.018", SRC)
        self.assertIn("size * 0.1908, size * 0.0882", SRC)
        self.assertNotIn("size * 0.212, size * 0.098", SRC)

    def test_outer_circle_only_uses_approved_wc_cyan(self):
        # Match the launcher Wc cyan exactly; outer rim alone is recolored.
        self.assertIn("Color32::from_rgb(122, 216, 252)", SRC)
        self.assertIn("WC_ANDROID6_APPROVED_CYAN_OUTER_RING_V1", SRC)
        self.assertIn("painter.circle_stroke(center, radius, Stroke::new(1.5, CYAN));", SRC)
        # Inner hub and existing muted sector seams stay untouched.
        self.assertIn("radius * 0.37, Stroke::new(1.6, CYAN)", SRC)
        self.assertIn("Color32::from_gray(89)", SRC)
        self.assertIn("Color32::from_black_alpha(alpha)", SRC)
        self.assertNotIn("painter.circle_stroke(center, radius, Stroke::new(1.0, Color32::from_gray(124)))", SRC)

    def test_soft_feather_shadow_without_other_wheel_changes(self):
        # Keep the same circle and PhotoCraft-style input geometry. Only
        # replace the old four thick halo bands with subtle fine layering.
        self.assertIn("WC_ANDROID7_SOFT_FEATHER_SHADOW_V1", SRC)
        self.assertIn("for step in 0..16 {", SRC)
        self.assertIn("14.0 - step as f32 * 0.8", SRC)
        self.assertIn("if step < 10 { 1 } else { 2 }", SRC)
        self.assertIn("center + egui::vec2(0.6, 1.4)", SRC)
        self.assertNotIn("[(17.0, 3), (12.0, 5), (7.0, 7), (3.0, 10)]", SRC)
        self.assertIn("painter.circle_stroke(center, radius, Stroke::new(1.5, CYAN));", SRC)
        self.assertIn("Color32::from_gray(89)", SRC)
        self.assertIn("radius * 0.37", SRC)

    def test_full_size_preview_and_customization(self):
        for text in ("170.0, 380.0, 215.0", "0.25, 1.0, 215.0", "Reset to default",
                     "Edit shortcuts", "wc_stylus_preview_popout",
                     "Wheel size", "Wheel opacity", "config_json"):
            self.assertIn(text, SRC)

    def test_popout_preview_only_when_adjusting_no_dialog_wheel(self):
        # The same full-size painter is used but in an independent top-level
        # overlay. Its timer is neither persisted nor attached to the document.
        for text in (
            "WC_ANDROID8_POPOUT_LIVE_PREVIEW_V1",
            "preview_last_adjust",
            "when.elapsed() < std::time::Duration::from_millis(3200)",
            "let settings_window = egui::Window::new",
            "if changed {",
            "self.preview_last_adjust = Some(std::time::Instant::now());",
            'egui::Id::new("wc_stylus_preview_popout")',
            ".order(egui::Order::Tooltip)",
            ".interactable(false)",
            "self.preview_owns(pos)",
            "self.preview_last_adjust = None;",
            "self.preview_center = None;",
            "self.size, self.opacity, Some(self.active)",
        ):
            self.assertIn(text, SRC)
        self.assertNotIn("egui::ScrollArea::horizontal().max_height(402.0)", SRC)
        self.assertNotIn('ui.label("Live preview (same geometry', SRC)
        # The floating preview is rendered after the settings Window returns,
        # not inside the window callback that contains slider controls.
        close_dialog = SRC.index("self.settings_open = open && !done_clicked;")
        overlay = SRC.index('egui::Id::new("wc_stylus_preview_popout")')
        self.assertLess(close_dialog, overlay)
        # Wheel and settings still use the exact same painting implementation.
        self.assertIn("self.paint(ui.ctx(), ui.painter(), rect.center(),", SRC)


    def test_android10_deckcraft_style_dialog_only(self):
        # The old self-referential description was explicitly removed.
        self.assertNotIn("Default • WordCraft blue/cyan • PhotoCraft layout", SRC)
        self.assertIn("WC_ANDROID10_POLISHED_CUSTOMIZATION_DIALOG_V1", SRC)
        self.assertIn('egui::Window::new("Customize Stylus Wheel")', SRC)
        self.assertIn('egui::RichText::new("Appearance")', SRC)
        self.assertIn('egui::RichText::new("Edit shortcuts")', SRC)
        self.assertIn("egui::Frame::group(ui.style())", SRC)
        self.assertIn("egui::Margin::same(12)", SRC)
        self.assertIn("egui::Margin::symmetric(10, 5)", SRC)
        self.assertIn("for slot in 0..8 {", SRC)
        self.assertIn("ui.add_sized([90.0, 30.0]", SRC)
        self.assertIn('egui::RichText::new("Done")', SRC)
        self.assertIn("self.settings_open = open && !done_clicked;", SRC)
        self.assertIn("if ui.button(\"Reset to default\").clicked()", SRC)
        # Core 200pt / 100%, two greys, 90%-scale Wc, cyan rim,
        # 16-step soft shadow, hover, and floating live preview are retained.
        for anchor in (
            "const DEFAULT_WHEEL_SIZE: f32 = 200.0;",
            "const DEFAULT_WHEEL_OPACITY: f32 = 1.0;",
            "SEGMENT_GREY_LIGHT",
            "SEGMENT_GREY_DARK",
            "size * 0.1908, size * 0.0882",
            "painter.circle_stroke(center, radius, Stroke::new(1.5, CYAN));",
            "WC_ANDROID7_SOFT_FEATHER_SHADOW_V1",
            "WC_ANDROID8_POPOUT_LIVE_PREVIEW_V1",
            "self.pen_hover.and_then(|p|",
        ):
            self.assertIn(anchor, SRC)

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
                     "Event::PointerGone", "self.owns", "raw.events = safe_events",
                     "MouseWheel", "WC_WHEEL_MODAL_ISOLATION_V2"):
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
        self.assertIn("✓ Stylus Wheel ON", MENU)
        self.assertIn("Open Stylus Wheel", MENU)
        self.assertIn("Customize Stylus Wheel", MENU)
        self.assertIn("wc_menu_wheel_visible", MENU)
        self.assertIn("WC_ANDROID4_VISIBLE_SETTINGS_SLIDERS_V1", SRC)
        self.assertIn("ui, &mut self.size, 170.0, 380.0, 215.0", SRC)
        self.assertIn("ui, &mut self.opacity, 0.25, 1.0, 215.0", SRC)
        self.assertIn("Adjust a slider or shortcut to see the wheel preview", SRC)
        self.assertIn("self.pen_hover.and_then(|p|", SRC)
        self.assertIn("self.sector(p, screen)", SRC)
        self.assertIn("WC_ANDROID4_REFINED_HISTORY_ARROWS_V1", SRC)
        self.assertIn('ui.menu_button("Stylus Wheel", |ui| {', MENU)
        self.assertIn('ui.checkbox(&mut pad, "Show Shortcut Pad")', MENU)
        self.assertEqual(MENU.count('ui.checkbox(&mut pad, "Show Shortcut Pad")'), 1)
        # Regression: wheel menu does not own the generic Shortcut Pad.
        wc_wheel_menu_start = MENU.index('ui.menu_button("Stylus Wheel", |ui| {')
        keyboard_menu_start = MENU.index('ui.menu_button("Keyboard & Shortcuts", |ui| {')
        pad_toggle_pos = MENU.index('ui.checkbox(&mut pad, "Show Shortcut Pad")')
        about_menu_start = MENU.index('ui.menu_button("About WordCraft", |ui| {')
        self.assertLess(wc_wheel_menu_start, keyboard_menu_start)
        self.assertLess(keyboard_menu_start, pad_toggle_pos)
        self.assertLess(pad_toggle_pos, about_menu_start)
        self.assertIn("WC_ANDROID5_SHORTCUT_PAD_MENU_MOVE_V1", MENU)

        self.assertIn("mod stylus_wheel;", NATIVE)
        self.assertIn("stylus_wheel.rs", BUILDER)
        self.assertIn("stylus_wheel_wc.rgba", BUILDER)
        self.assertIn("WC_EXACT_LAUNCHER_WC_GLYPH_V1", BUILDER)
        self.assertIn("WC_APPROVED_WC_LAUNCHER_GLYPH_V1", SRC)
        self.assertIn("radius * 0.37", SRC)
        self.assertIn("PhotoCraft hub ratio", SRC)
        self.assertIn("wcWheelHandlePenKey", JAVA)
        self.assertIn("wcWheelButtonMotion", JAVA)
        self.assertIn("KEYCODE_DPAD_DOWN", JAVA)
        self.assertIn("wcWheelPoll", JAVA)
        self.assertIn("wcWheelSetEnabled", JAVA)
        self.assertIn("wcWheelPoll", NATIVE)
        self.assertIn("self.poll_wheel(ctx);", NATIVE)
        self.assertIn("WC_ANDROID4_STYLUS_CATEGORY_V1", MENU)

    def test_no_production_or_cross_app_mutation(self):
        self.assertNotIn("MANAGE_EXTERNAL_STORAGE", SRC)
        self.assertNotIn("keystore", SRC.lower())
        self.assertNotIn("publish", SRC.lower())
        self.assertTrue((ROOT / "patch_touch_guard.py").is_file())


if __name__ == "__main__":
    unittest.main()
