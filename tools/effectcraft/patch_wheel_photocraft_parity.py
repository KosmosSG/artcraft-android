#!/usr/bin/env python3
"""EffectCraft Android.3: PhotoCraft style parity on the disposable source checkout.

Reference: approved PhotoCraft v0.23.1-android.5 wheel (Nov 2026).
Do not change the existing EffectCraft 8 commands, pen routing, colour branding,
user preference storage, actual-size preview or production keystore.
"""
from pathlib import Path
import sys

def once(source, old, new, name):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"STOP: {name} anchor changed ({count} matches): {old[:85]!r}")
    return source.replace(old, new, 1)

TOAST = r'''
    pub(crate) fn notify(&mut self, message: &'static str) {
        self.feedback_message = message;
        self.feedback_at = Instant::now();
    }

    /// PhotoCraft's bottom-center, non-interactive notification pill:
    /// visible 1900ms, fading 500ms, 350x31pt, 13pt corner rounding.
    fn paint_feedback(&self, ctx: &Context) {
        let elapsed = self.feedback_at.elapsed();
        if elapsed >= FEEDBACK_HOLD + FEEDBACK_FADE { return; }
        let fade = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
            1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32()
                / FEEDBACK_FADE.as_secs_f32()
        }.clamp(0.0, 1.0);
        let screen = ctx.content_rect();
        let width = 350.0f32.min((screen.width() - 24.0).max(90.0));
        let height = 31.0;
        let top = (screen.bottom() - 43.0).max(screen.top());
        egui::Area::new(Id::new("ec-wheel-bottom-feedback"))
            .order(Order::Foreground)
            .fixed_pos(pos2(screen.center().x - width * 0.5, top))
            .interactable(false)
            .show(ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(width, height), Sense::hover());
                let painter = ui.painter_at(rect);
                painter.rect_filled(rect, 13.0,
                    Color32::from_rgba_unmultiplied(49, 49, 51,
                        (244.0 * fade) as u8));
                painter.rect_stroke(rect, 13.0,
                    Stroke::new(1.0, Color32::from_rgba_unmultiplied(
                        105, 105, 109, (135.0 * fade) as u8)),
                    egui::StrokeKind::Inside);
                painter.text(rect.center(), egui::Align2::CENTER_CENTER,
                    self.feedback_message, FontId::proportional(11.0),
                    Color32::WHITE.gamma_multiply(fade));
            });
        ctx.request_repaint_after(Duration::from_millis(45));
    }
'''

APP_UPDATES_OLD = '''                        for (title, key) in [
                            ("Check for Updates", "artcraft.effectcraft.check_updates_requested"),
                            ("Startup Update Check", "artcraft.effectcraft.update_settings_requested"),
                        ] {
                            if ui.button(title).clicked() {
                                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                                ui.close();
                            }
                        }'''
APP_UPDATES_NEW = '''                        ui.menu_button("App Updates", |ui| {
                            ui.set_min_width(218.0);
                            for (label, key) in [
                                ("Check for Updates", "artcraft.effectcraft.check_updates_requested"),
                                ("Startup Update Check…", "artcraft.effectcraft.update_settings_requested"),
                            ] {
                                if ui.button(label).clicked() {
                                    ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new(key), true));
                                    ui.close();
                                }
                            }
                        });'''
WHEEL_MENU_OLD = '''                        let wheel_on = app.stylus_wheel.enabled;
                        if ui.button(if wheel_on {
                            "✓ Stylus Wheel ON"
                        } else {
                            "Stylus Wheel OFF"
                        }).clicked() {
                            app.stylus_wheel.toggle(ui.ctx());
                            ui.close();
                        }
                        if ui.add_enabled(wheel_on, egui::Button::new("Open Stylus Wheel")).clicked() {
                            app.stylus_wheel.open_at_hover(ui.ctx());
                            ui.close();
                        }
                        if ui.button("Customize Stylus Wheel…").clicked() {
                            app.stylus_wheel.settings_open = true;
                            ui.close();
                        }'''
WHEEL_MENU_NEW = '''                        ui.menu_button("Stylus Wheel", |ui| {
                            ui.set_min_width(221.0);
                            let wheel_on = app.stylus_wheel.enabled;
                            if ui.button(if wheel_on {
                                "✓ Enable Stylus Wheel"
                            } else {
                                "   Enable Stylus Wheel"
                            }).clicked() {
                                app.stylus_wheel.toggle(ui.ctx());
                                ui.close();
                            }
                            if ui.add_enabled(wheel_on,
                                egui::Button::new("Open Stylus Wheel")).clicked() {
                                app.stylus_wheel.open_at_hover(ui.ctx());
                                ui.close();
                            }
                            if ui.button("Customize Stylus Wheel…").clicked() {
                                app.stylus_wheel.settings_open = true;
                                app.stylus_wheel.notify("Wheel settings • live preview");
                                ui.close();
                            }
                        });'''

def patch(root: Path):
    source = Path(root) / "source/effectcraft/crates/ui-egui/src"
    wheel = source / "stylus_wheel.rs"
    header = source / "header.rs"
    src = wheel.read_text(encoding="utf-8")
    old = src
    src = once(src, "const SIZE: f32 = 312.0;",
        "const SIZE: f32 = 312.0;\nconst FEEDBACK_HOLD: Duration = Duration::from_millis(1900);\nconst FEEDBACK_FADE: Duration = Duration::from_millis(500);", "wheel feedback timing")
    src = once(src, "    last_press: Option<Instant>,",
        "    last_press: Option<Instant>,\n    feedback_message: &'static str,\n    feedback_at: Instant,", "feedback state")
    src = once(src, "            storage: None, pending: None, last_press: None,",
        "            storage: None, pending: None, last_press: None,\n"
        "            feedback_message: \"\", feedback_at: Instant::now() - FEEDBACK_HOLD - FEEDBACK_FADE,",
        "feedback initialization")
    src = once(src, "    fn scale(&self) -> f32 { self.size_percent / 100.0 }",
        "    fn scale(&self) -> f32 { self.size_percent / 100.0 }\n" + TOAST,
        "feedback painter")
    src = once(src, "        self.enabled = !self.enabled;\n        self.open = false;",
        '        self.enabled = !self.enabled;\n'
        '        self.notify(if self.enabled { "Wheel ON • hover + stylus button" } else { "Wheel OFF" });\n'
        '        self.open = false;', "wheel toggle notification")
    src = once(src, "        self.open = true;\n        ctx.request_repaint();",
        '        self.open = true;\n'
        '        self.notify("Hover to highlight • tap tip to select");\n'
        '        ctx.request_repaint();', "wheel open notification")
    src = once(src, "    pub(crate) fn render(&mut self, ctx: &Context) {\n        self.customize(ctx);",
        "    pub(crate) fn render(&mut self, ctx: &Context) {\n        self.customize(ctx);\n        self.paint_feedback(ctx);", "bottom notification integration")
    src = once(src,
        '                ui.label("PhotoCraft-style Default · 8 customizable segments");\n'
        '                ui.label("The preview is at actual wheel size.");',
        '                ui.label("Style: Default  •  8 segments");\n'
        '                ui.label("Choose a tool for each position. Existing selections swap positions.");',
        "PhotoCraft dialog introduction")
    src = once(src, '                ui.label("Magic-Pencil 4s: press to open • press again to close");',
        '                ui.separator();\n'
        '                ui.label("Actual-size preview appears beside this window.");\n'
        '                ui.label("75–125% size and opacity match the real Stylus Wheel.");\n'
        '                ui.label("Pen button: single opens wheel, double selects Hand.");',
        "PhotoCraft dialog footer")
    shadow_start = src.index("        // Broad translucent rings yield the PhotoCraft soft shadow")
    shadow_end = src.index("        for slot in 0..8 {", shadow_start)
    src = src[:shadow_start] + '''        // PhotoCraft compact feathered shadow: no hard grey halo.
        for step in 0..12 {
            let spread = (12.0 - step as f32 * 0.82) * scale;
            let softness = 0.008 + step as f32 * 0.0017;
            painter.circle_filled(center + vec2(0.8, 2.0) * scale,
                R * scale + spread, Color32::BLACK.gamma_multiply(softness));
        }
''' + src[shadow_end:]
    src = once(src, "Color32::from_rgba_unmultiplied(46, 58, 210,",
        "Color32::from_rgba_unmultiplied(28, 85, 192,", "EffectCraft blue highlight")
    src = once(src,
        '''if slot % 2 == 0 { 72 } else { 66 },
                    if slot % 2 == 0 { 72 } else { 66 },
                    if slot % 2 == 0 { 78 } else { 73 },''',
        '''if slot % 2 == 0 { 43 } else { 51 },
                    if slot % 2 == 0 { 43 } else { 51 },
                    if slot % 2 == 0 { 45 } else { 54 },''',
        "PhotoCraft two-tone dark grey petals")
    src = once(src, "Stroke::new(0.6, Color32::from_gray(102))",
        "Stroke::new(0.65, Color32::from_gray(72))", "PhotoCraft fine strokes")
    src = once(src, "Stroke::new(0.8, Color32::from_gray(112))",
        "Stroke::new(0.8, Color32::from_gray(74))", "PhotoCraft thin outer rim")
    src = once(src, 'selected.map(|slot| LABELS[self.slots[slot]]).unwrap_or("EffectCraft"),',
        'selected.map(|slot| LABELS[self.slots[slot]]).unwrap_or("Default"),', "hub label")
    # Do not introduce a second icon pack; Android.2's custom curve renderer is
    # kept so Undo/Redo remain curved, not playback skip arrows.
    if 'include_bytes!("stylus_wheel_ec.rgba")' not in src or \
            'fn paint_slot_icon' not in src or 'pen_hover' not in src:
        raise RuntimeError("STOP: approved Ec logo, icon refinement, or stylus hover missing")
    h = header.read_text(encoding="utf-8")
    h = once(h, APP_UPDATES_OLD, APP_UPDATES_NEW, "nested app updater submenu")
    h = once(h, WHEEL_MENU_OLD, WHEEL_MENU_NEW, "PhotoCraft stylus wheel submenu")
    assert len(src) > len(old)
    wheel.write_text(src, encoding="utf-8")
    header.write_text(h, encoding="utf-8")
    print("PASS: PhotoCraft layout/default 100%/85%, two-tone segments, soft shadow, dialog, Ec submenu and bottom-centered toast")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("Usage: patch_wheel_photocraft_parity.py <builder-root>")
    patch(Path(sys.argv[1]))
