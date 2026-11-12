//! CADCraft Android stylus wheel, adapted to upstream egui without modifying desktop UI.
//! Uses native command IDs, not fake tool buttons. No Java permissions or broad input hooks.
use crate::CadApp;
use egui::{self, Align2, Color32, FontId, Id, Pos2, Rect, Sense, Stroke, Vec2};

pub const ACTIONS: [(&str, &str); 14] = [
    ("Select", "select"), ("Line", "line"), ("Circle", "circle"),
    ("Layers", "ui.panel.layers"), ("Hand", "pan"), ("Trim", "trim"),
    ("Redo", "redo"), ("Undo", "undo"), ("Snap", "osnap"),
    ("Polyline", "pline"), ("Move", "move"), ("Erase", "erase"),
    ("Measure", "dist"), ("Command Line", "ui.toggle.cmdline"),
];
pub const DEFAULT_ACTIONS: [&str; 8] =
    ["select", "line", "circle", "ui.panel.layers", "pan", "trim", "redo", "undo"];
const BRAND: Color32 = Color32::from_rgb(209, 49, 83);
const CREAM: Color32 = Color32::from_rgb(243, 228, 231);
const FULL: f32 = std::f32::consts::TAU;
const SECTORS: f32 = 8.0;

pub fn valid_action(id: &str) -> bool {
    ACTIONS.iter().any(|(_, command)| id == *command)
}
fn label(id: &str) -> &str {
    ACTIONS.iter().find(|(_, command)| id == *command)
        .map_or("Select", |(name, _)| *name)
}
pub fn default_actions() -> Vec<String> {
    DEFAULT_ACTIONS.iter().map(|s| (*s).to_string()).collect()
}

// The only image source is the user's reviewed, exact-red Cc artwork. The
// Python source overlay rasterizes it to 64x64 RGBA before the Android compile.
fn icon_texture(ctx: &egui::Context) -> egui::TextureHandle {
    let id = Id::new("cadcraft_android_cc_icon_texture_v2");
    if let Some(found) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
        return found;
    }
    let img = egui::ColorImage::from_rgba_unmultiplied(
        [64, 64], include_bytes!("cadcraft_cc_icon.rgba"),
    );
    let handle = ctx.load_texture("cadcraft-cc-exact-brand-v2", img, egui::TextureOptions::LINEAR);
    ctx.data_mut(|d| d.insert_temp(id, handle.clone()));
    handle
}
fn paint_cc(ui: &egui::Ui, rect: Rect) {
    let tex = icon_texture(ui.ctx());
    ui.painter().image(
        tex.id(), rect, Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)),
        Color32::WHITE,
    );
}

/// Compact PhotoCraft-style Cc menu; intentionally no "CADCraft Android" title,
/// no global-upstream updater and no diagnostics menu.
pub fn cc_menu(app: &mut CadApp, ui: &mut egui::Ui, clicked: &mut Option<String>) {
    let (icon_rect, response) = ui.allocate_exact_size(Vec2::new(24.0, 21.0), Sense::click());
    paint_cc(ui, icon_rect.shrink(1.5));
    let response = response.on_hover_text("CADCraft");
    egui::Popup::menu(&response).show(|ui| {
        ui.set_min_width(216.0);
        ui.menu_button("Appearance", |ui| {
            for (name, cmd) in [
                ("Follow System", "ui.theme.system"),
                ("Light", "ui.theme.light"),
                ("Dark", "ui.theme.dark"),
            ] {
                if ui.button(name).clicked() {
                    *clicked = Some(cmd.to_string());
                    ui.close();
                }
            }
        });
        ui.separator();
        // Upstream's update checker points at the official desktop app, not
        // this test package. Never present it as a working Android APK updater.
        ui.menu_button("App Updates", |ui| {
            ui.set_min_width(238.0);
            ui.add_enabled(false, egui::Button::new("No published CADCraft Android release"));
        });
        ui.menu_button("Stylus Wheel", |ui| {
            if ui.checkbox(&mut app.ui.cad_wheel_open, "Show Stylus Wheel").clicked() {
                ui.close();
            }
            if ui.button("Customize Wheel...").clicked() {
                app.ui.cad_wheel_customize = true;
                ui.close();
            }
            if ui.button("Reset to CAD Defaults").clicked() {
                app.ui.cad_wheel_actions = default_actions();
                ui.close();
            }
        });
        if ui.button("Keyboard Shortcuts...").clicked() {
            *clicked = Some("ui.shortcuts".to_string());
            ui.close();
        }
        ui.separator();
        if ui.button("About CADCraft").clicked() {
            *clicked = Some("ui.dialog.about".to_string());
            ui.close();
        }
    });
    ui.separator();
}

fn wheel_index(pos: Pos2, center: Pos2, radius: f32) -> Option<usize> {
    let d = pos - center;
    let r = d.length();
    if !(48.0..=radius).contains(&r) {
        return None;
    }
    let sector = FULL / SECTORS;
    let a = (d.y.atan2(d.x) + std::f32::consts::FRAC_PI_2 + sector / 2.0).rem_euclid(FULL);
    Some(((a / sector).floor() as usize).min(7))
}
fn draw_glyph(painter: &egui::Painter, action: &str, pos: Pos2, stroke: Stroke) {
    let line = |a: Vec2, b: Vec2| painter.line_segment([pos + a, pos + b], stroke);
    match action {
        "line" | "pline" => {
            line(Vec2::new(-11.0, 8.0), Vec2::new(11.0, -8.0));
            painter.circle_filled(pos + Vec2::new(-11.0, 8.0), 2.5, CREAM);
            painter.circle_filled(pos + Vec2::new(11.0, -8.0), 2.5, CREAM);
        }
        "circle" => { painter.circle_stroke(pos, 11.0, stroke); }
        "ui.panel.layers" => {
            for y in [-6.0, 0.0, 6.0] {
                line(Vec2::new(-12.0, y), Vec2::new(0.0, y + 6.0));
                line(Vec2::new(0.0, y + 6.0), Vec2::new(12.0, y));
            }
        }
        "select" => {
            painter.line_segment([pos + Vec2::new(-7.0,-12.0), pos + Vec2::new(10.0,6.0)], stroke);
            painter.line_segment([pos + Vec2::new(-7.0,-12.0), pos + Vec2::new(-7.0,12.0)], stroke);
            painter.line_segment([pos + Vec2::new(-7.0,12.0), pos + Vec2::new(0.0,6.0)], stroke);
        }
        "pan" => { painter.text(pos, Align2::CENTER_CENTER, "✋", FontId::proportional(23.0), CREAM); }
        "trim" => { painter.text(pos, Align2::CENTER_CENTER, "✂", FontId::proportional(23.0), CREAM); }
        "undo" => { painter.text(pos, Align2::CENTER_CENTER, "↶", FontId::proportional(29.0), CREAM); }
        "redo" => { painter.text(pos, Align2::CENTER_CENTER, "↷", FontId::proportional(29.0), CREAM); }
        "osnap" => {
            painter.circle_stroke(pos, 9.0, stroke);
            line(Vec2::new(-15.0,0.0),Vec2::new(15.0,0.0));
            line(Vec2::new(0.0,-15.0),Vec2::new(0.0,15.0));
        }
        _ => {
            painter.text(pos, Align2::CENTER_CENTER, "⌘", FontId::proportional(21.0), CREAM);
        }
    }
}
fn draw_ring(ui: &mut egui::Ui, center: Pos2, radius: f32, selected: Option<usize>, actions: &[String]) {
    let painter = ui.painter();
    painter.circle_filled(center + Vec2::new(0.0, 5.0), radius + 5.0, Color32::from_black_alpha(60));
    let sector = FULL / SECTORS;
    for k in 0..8 {
        let angle = -std::f32::consts::FRAC_PI_2 + (k as f32) * sector;
        let begin = angle - sector / 2.0;
        let mut points = vec![center];
        for step in 0..=14 {
            let a = begin + sector * (step as f32 / 14.0);
            points.push(center + Vec2::new(a.cos(), a.sin()) * radius);
        }
        let active = selected == Some(k);
        let fill = if active { BRAND } else { Color32::from_rgb(49, 50, 57) };
        painter.add(egui::Shape::convex_polygon(points, fill, Stroke::new(0.8, Color32::from_gray(100))));
        let p = center + Vec2::new(angle.cos(), angle.sin()) * 96.0;
        let action = actions.get(k).map_or(DEFAULT_ACTIONS[k], String::as_str);
        draw_glyph(painter, action, p + Vec2::new(0.0, -9.0), Stroke::new(2.0, CREAM));
        painter.text(p + Vec2::new(0.0, 19.0), Align2::CENTER_CENTER, label(action), FontId::proportional(11.5), CREAM);
    }
    painter.circle_filled(center, 48.0, Color32::from_rgb(35, 35, 41));
    painter.circle_stroke(center, 49.0, Stroke::new(2.0, BRAND));
    paint_cc(ui, Rect::from_center_size(center, Vec2::splat(63.0)));
}

/// Draw after the canvas and before modal prompts so the wheel gets foreground
/// hit-testing and doesn't create a CAD selection underneath the ring.
pub fn show(app: &mut CadApp, ctx: &egui::Context) {
    if app.ui.cad_wheel_customize {
        let mut open = true;
        egui::Window::new("Customize CADCraft Stylus Wheel")
            .id(Id::new("cadcraft_android_wheel_customize"))
            .open(&mut open)
            .resizable(false)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.label("Choose the native CAD command for each wheel segment.");
                ui.separator();
                for idx in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", idx + 1));
                        let current = app.ui.cad_wheel_actions.get(idx)
                            .map_or(DEFAULT_ACTIONS[idx], String::as_str);
                        egui::ComboBox::from_id_salt(("cadcraft_wheel_slot", idx))
                            .selected_text(label(current))
                            .width(145.0)
                            .show_ui(ui, |ui| {
                                for (name, id) in ACTIONS {
                                    if ui.selectable_label(current == id, name).clicked() {
                                        if let Some(slot) = app.ui.cad_wheel_actions.get_mut(idx) {
                                            *slot = id.to_string();
                                        }
                                    }
                                }
                            });
                    });
                }
                ui.separator();
                if ui.button("Reset to CAD Defaults").clicked() {
                    app.ui.cad_wheel_actions = default_actions();
                }
            });
        app.ui.cad_wheel_customize = open;
    }

    let bounds = ctx.available_rect();
    if !app.ui.cad_wheel_open {
        // A small unobtrusive, accessible launcher remains on screen; users can
        // also open the wheel via Cc ▸ Stylus Wheel. No CAD right-click hijack.
        let pos = Pos2::new((bounds.max.x - 55.0).max(4.0), (bounds.max.y - 81.0).max(4.0));
        egui::Area::new(Id::new("cadcraft_android_wheel_launcher"))
            .order(egui::Order::Foreground).fixed_pos(pos).show(ctx, |ui| {
                let (rect, response) = ui.allocate_exact_size(Vec2::splat(42.0), Sense::click());
                ui.painter().circle_filled(rect.center(), 22.0, Color32::from_black_alpha(75));
                paint_cc(ui, rect.shrink(5.0));
                if response.on_hover_text("Open CADCraft Stylus Wheel").clicked() {
                    app.ui.cad_wheel_open = true;
                }
            });
        return;
    }

    let pos = Pos2::new((bounds.max.x - 320.0).max(4.0), (bounds.max.y - 366.0).max(4.0));
    let mut chosen: Option<String> = None;
    egui::Area::new(Id::new("cadcraft_android_stylus_wheel"))
        .order(egui::Order::Foreground)
        .fixed_pos(pos)
        .show(ctx, |ui| {
            let (rect, response) = ui.allocate_exact_size(Vec2::new(308.0, 342.0), Sense::click());
            let center = rect.left_top() + Vec2::new(154.0, 150.0);
            let cursor = ctx.input(|i| i.pointer.hover_pos());
            let hovered = cursor.and_then(|p| wheel_index(p, center, 137.0));
            draw_ring(ui, center, 137.0, hovered, &app.ui.cad_wheel_actions);
            if let Some(where_at) = cursor {
                if (where_at - center).length() < 47.0 {
                    ui.painter().circle_stroke(center, 46.0, Stroke::new(2.5, CREAM));
                }
            }
            let note = Rect::from_center_size(rect.left_top() + Vec2::new(154.0, 316.0), Vec2::new(298.0, 28.0));
            ui.painter().rect_filled(note, 15.0, Color32::from_rgba_unmultiplied(73, 74, 80, 230));
            ui.painter().text(note.center(), Align2::CENTER_CENTER, "Hover to highlight • tap tip to select", FontId::proportional(12.0), CREAM);
            if response.clicked() {
                if let Some(at) = cursor {
                    if (at - center).length() < 47.0 {
                        app.ui.cad_wheel_open = false;
                    } else if let Some(idx) = wheel_index(at, center, 137.0) {
                        chosen = app.ui.cad_wheel_actions.get(idx).cloned();
                        app.ui.cad_wheel_open = false;
                    }
                }
            }
        });
    if let Some(cmd) = chosen {
        if app.session.docs.is_empty() && !cmd.starts_with("ui.") {
            app.set_status("Create or open a drawing before using CAD tools.");
        } else {
            crate::menus::activate(app, &cmd);
        }
    }
}
