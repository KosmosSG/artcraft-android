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
        tex.id(), rect, Rect::from_min_max(Pos2::new(0.0, 0.0), Pos2::new(1.0, 1.0)),
        Color32::WHITE,
    );
}

fn tinted(color: Color32, opacity: f32) -> Color32 {
    Color32::from_rgba_unmultiplied(color.r(), color.g(), color.b(),
        (color.a() as f32 * opacity.clamp(0.0, 1.0)).round() as u8)
}

// Transparent Cc glyph: center is a solid circular brand-colored hub, not an
// inset rounded-square launcher icon. Generated from the same reviewed SVG.
fn center_glyph_texture(ctx: &egui::Context) -> egui::TextureHandle {
    let id = Id::new("cadcraft_android_cc_center_glyph_v3");
    if let Some(found) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
        return found;
    }
    let image = egui::ColorImage::from_rgba_unmultiplied(
        [64, 64], include_bytes!("cadcraft_cc_glyph.rgba"),
    );
    let handle = ctx.load_texture("cadcraft-cc-cream-glyph-v3", image, egui::TextureOptions::LINEAR);
    ctx.data_mut(|d| d.insert_temp(id, handle.clone()));
    handle
}
fn paint_center_glyph(ui: &egui::Ui, rect: Rect, opacity: f32) {
    let tex = center_glyph_texture(ui.ctx());
    ui.painter().image(tex.id(), rect,
        Rect::from_min_max(Pos2::new(0.0, 0.0), Pos2::new(1.0, 1.0)),
        tinted(Color32::WHITE, opacity));
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
        // Invoke the CADCraft-only Java updater from the native app, never
        // the Android reference builder's unrelated global release feed.
        if ui.button("Check for Updates...").clicked() {
            crate::cadcraft_android_wheel::check_cadcraft_updates();
            ui.close();
        }
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
                app.ui.cad_wheel_size = 1.0;
                app.ui.cad_wheel_opacity = 1.0;
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
    if !(48.0 * radius / 137.0..=radius).contains(&r) {
        return None;
    }
    let sector = FULL / SECTORS;
    let a = (d.y.atan2(d.x) + std::f32::consts::FRAC_PI_2 + sector / 2.0).rem_euclid(FULL);
    Some(((a / sector).floor() as usize).min(7))
}
fn draw_glyph(painter: &egui::Painter, action: &str, pos: Pos2, stroke: Stroke, cream: Color32) {
    let line = |a: Vec2, b: Vec2| painter.line_segment([pos + a, pos + b], stroke);
    match action {
        "line" | "pline" => {
            line(Vec2::new(-11.0, 8.0), Vec2::new(11.0, -8.0));
            painter.circle_filled(pos + Vec2::new(-11.0, 8.0), 2.5, cream);
            painter.circle_filled(pos + Vec2::new(11.0, -8.0), 2.5, cream);
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
        "pan" => { painter.text(pos, Align2::CENTER_CENTER, "✋", FontId::proportional(23.0), cream); }
        "trim" => { painter.text(pos, Align2::CENTER_CENTER, "✂", FontId::proportional(23.0), cream); }
        "undo" => { painter.text(pos, Align2::CENTER_CENTER, "↶", FontId::proportional(29.0), cream); }
        "redo" => { painter.text(pos, Align2::CENTER_CENTER, "↷", FontId::proportional(29.0), cream); }
        "osnap" => {
            painter.circle_stroke(pos, 9.0, stroke);
            line(Vec2::new(-15.0,0.0),Vec2::new(15.0,0.0));
            line(Vec2::new(0.0,-15.0),Vec2::new(0.0,15.0));
        }
        _ => {
            painter.text(pos, Align2::CENTER_CENTER, "⌘", FontId::proportional(21.0), cream);
        }
    }
}
fn draw_ring(ui: &mut egui::Ui, center: Pos2, radius: f32, selected: Option<usize>, actions: &[String], opacity: f32) {
    let painter = ui.painter();
    let scale = radius / 137.0;
    let cream = tinted(CREAM, opacity);
    let brand = tinted(BRAND, opacity);
    let shadow = Color32::from_black_alpha((38.0 * opacity) as u8);
    painter.circle_filled(center + Vec2::new(0.0, 3.0 * scale), radius + 3.0 * scale, shadow);
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
        let fill = if active { brand } else { tinted(Color32::from_rgb(69, 67, 73), opacity) };
        painter.add(egui::Shape::convex_polygon(points, fill,
            Stroke::new(0.8, tinted(Color32::from_gray(110), opacity))));
        let p = center + Vec2::new(angle.cos(), angle.sin()) * (96.0 * scale);
        let action = actions.get(k).map_or(DEFAULT_ACTIONS[k], String::as_str);
        draw_glyph(painter, action, p + Vec2::new(0.0, -9.0 * scale),
            Stroke::new(2.0 * scale, cream), cream);
        painter.text(p + Vec2::new(0.0, 19.0 * scale), Align2::CENTER_CENTER,
            label(action), FontId::proportional((11.5 * scale).max(8.5)), cream);
    }
    // PhotoCraft-like continuous circle, customized to the exact Cc pink.
    let hub = 48.0 * scale;
    painter.circle_filled(center, hub, brand);
    painter.circle_stroke(center, hub + 1.0 * scale, Stroke::new(2.0 * scale, cream));
    paint_center_glyph(ui, Rect::from_center_size(center, Vec2::splat(58.0 * scale)), opacity);
}

#[cfg(target_os = "android")]
pub fn check_cadcraft_updates() {
    // The Android app supplies the VM/Activity context. Do not invoke a
    // browser, download unsigned APKs, or query the reference builder feed.
    let context = ndk_context::android_context();
    let vm = unsafe { jni::JavaVM::from_raw(context.vm() as *mut _) };
    let result = vm.attach_current_thread(|env| -> jni::errors::Result<()> {
        let activity_raw = context.context() as jni::sys::jobject;
        let activity = unsafe { env.as_cast_raw::<jni::objects::JObject>(&activity_raw)? };
        env.call_static_method(
            "com/artcraft/updater/UpdateCheck",
            "checkNow",
            jni::jni_sig!("(Landroid/app/Activity;)V"),
            &[jni::objects::JValue::Object(&activity)],
        )?;
        Ok(())
    });
    if let Err(error) = result {
        eprintln!("CADCraft update check not available: {error}");
    }
}

/// Draw after the canvas and before modal prompts so the wheel gets foreground
/// hit-testing and doesn't create a CAD selection underneath the ring.
pub fn show(app: &mut CadApp, ctx: &egui::Context, bounds: egui::Rect) {
    if app.ui.cad_wheel_customize {
        let mut open = true;
        egui::Window::new("Customize CADCraft Stylus Wheel")
            .id(Id::new("cadcraft_android_wheel_customize"))
            .open(&mut open)
            .resizable(false)
            .collapsible(false)
            .show(ctx, |ui| {
                ui.label("Configure eight CAD commands and preview the wheel live.");
                ui.separator();
                ui.horizontal(|ui| {
                    ui.vertical(|ui| {
                        ui.set_min_width(228.0);
                        for idx in 0..8 {
                            ui.horizontal(|ui| {
                                ui.label(format!("Slot {}", idx + 1));
                                let current = app.ui.cad_wheel_actions.get(idx)
                                    .cloned().unwrap_or_else(|| DEFAULT_ACTIONS[idx].to_owned());
                                egui::ComboBox::from_id_salt(("cadcraft_wheel_slot", idx))
                                    .selected_text(label(current.as_str()))
                                    .width(145.0)
                                    .show_ui(ui, |ui| {
                                        for (name, id) in ACTIONS {
                                            if ui.selectable_label(current.as_str() == id, name).clicked() {
                                                if let Some(slot) = app.ui.cad_wheel_actions.get_mut(idx) {
                                                    *slot = id.to_string();
                                                }
                                            }
                                        }
                                    });
                            });
                        }
                        ui.separator();
                        ui.label("Wheel size");
                        ui.add(egui::Slider::new(&mut app.ui.cad_wheel_size, 0.65..=1.45)
                            .custom_formatter(|n, _| format!("{:.0}%", n * 100.0)));
                        ui.label("Wheel opacity");
                        ui.add(egui::Slider::new(&mut app.ui.cad_wheel_opacity, 0.35..=1.0)
                            .custom_formatter(|n, _| format!("{:.0}%", n * 100.0)));
                        ui.separator();
                        if ui.button("Reset to CAD Defaults").clicked() {
                            app.ui.cad_wheel_actions = default_actions();
                            app.ui.cad_wheel_size = 1.0;
                            app.ui.cad_wheel_opacity = 1.0;
                        }
                    });
                    ui.separator();
                    ui.vertical(|ui| {
                        ui.label("Live preview · actual wheel size");
                        let radius = 137.0 * app.ui.cad_wheel_size.clamp(0.65, 1.45);
                        let dim = radius * 2.0 + 16.0;
                        let (preview_rect, _) = ui.allocate_exact_size(
                            Vec2::splat(dim), Sense::hover());
                        draw_ring(ui, preview_rect.center(), radius,
                            None, &app.ui.cad_wheel_actions, app.ui.cad_wheel_opacity);
                    });
                });
            });
        app.ui.cad_wheel_customize = open;
    }

    // Screen bounds come from the host Ui because pinned egui 0.37 has no Context::screen_rect.
    // No bottom-right Cc floating launcher. Wheel is opened from the top-left
    // Cc menu, keeping the drawing workspace unobstructed.
    if !app.ui.cad_wheel_open {
        return;
    }

    let radius = 137.0 * app.ui.cad_wheel_size.clamp(0.65, 1.45);
    let diameter = radius * 2.0;
    let width = diameter + 24.0;
    let pos = Pos2::new((bounds.max.x - width - 12.0).max(4.0),
        (bounds.max.y - width - 12.0).max(4.0));
    let mut chosen: Option<String> = None;
    egui::Area::new(Id::new("cadcraft_android_stylus_wheel"))
        .order(egui::Order::Foreground)
        .fixed_pos(pos)
        .show(ctx, |ui| {
            let (rect, response) = ui.allocate_exact_size(Vec2::splat(width), Sense::click());
            let center = rect.center();
            let cursor = ctx.input(|i| i.pointer.hover_pos());
            let hovered = cursor.and_then(|p| wheel_index(p, center, radius));
            draw_ring(ui, center, radius, hovered,
                &app.ui.cad_wheel_actions, app.ui.cad_wheel_opacity);
            let hub = 48.0 * radius / 137.0;
            if let Some(where_at) = cursor {
                if (where_at - center).length() < hub {
                    ui.painter().circle_stroke(center, hub,
                        Stroke::new(2.5, tinted(CREAM, app.ui.cad_wheel_opacity)));
                }
            }
            if response.clicked() {
                if let Some(at) = cursor {
                    if (at - center).length() < hub {
                        app.ui.cad_wheel_open = false;
                    } else if let Some(idx) = wheel_index(at, center, radius) {
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
