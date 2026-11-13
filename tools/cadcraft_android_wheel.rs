//! CADCraft Android stylus wheel, adapted to upstream egui without modifying desktop UI.
//! Uses native command IDs, not fake tool buttons. No Java permissions or broad input hooks.
use crate::CadApp;
use egui::{self, Align2, Color32, FontId, Id, Pos2, Rect, Sense, Stroke, Vec2};
use std::time::{Instant, Duration};

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
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const DEFAULT_SIZE: f32 = 1.0;
const DEFAULT_OPACITY: f32 = 0.85;
const WHEEL_SIZE: f32 = 312.0;
const RADIUS: f32 = 128.0;
const HUB: f32 = 48.0;

#[derive(Clone)]
struct Feedback { text: String, at: Instant }
fn notify(ctx: &egui::Context, text: &str) {
    ctx.data_mut(|d| d.insert_temp(
        Id::new("cadcraft-wheel-feedback"), Feedback { text: text.to_string(), at: Instant::now() }));
    ctx.request_repaint();
}
fn show_feedback(ctx: &egui::Context) {
    let Some(note) = ctx.data(|d| d.get_temp::<Feedback>(Id::new("cadcraft-wheel-feedback"))) else { return; };
    let elapsed = note.at.elapsed();
    if elapsed >= FEEDBACK_HOLD + FEEDBACK_FADE { return; }
    let alpha = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
        1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32() / FEEDBACK_FADE.as_secs_f32()
    }.clamp(0.0, 1.0);
    ctx.request_repaint_after(Duration::from_millis(45));
    let screen = ctx.content_rect();
    let width = 350.0_f32.min(screen.width() - 24.0);
    egui::Area::new(Id::new("cadcraft-wheel-bottom-feedback"))
        .order(egui::Order::Foreground)
        .interactable(false)
        .fixed_pos(Pos2::new(screen.center().x - width / 2.0, screen.bottom() - 43.0))
        .show(ctx, |ui| {
            let (rect, _) = ui.allocate_exact_size(Vec2::new(width, 31.0), Sense::hover());
            let p = ui.painter_at(rect);
            p.rect_filled(rect, 13.0,
                Color32::from_rgba_unmultiplied(56, 57, 63, (238.0 * alpha) as u8));
            p.rect_stroke(rect, 13.0,
                Stroke::new(1.0, Color32::from_rgba_unmultiplied(125, 119, 125, (105.0 * alpha) as u8)),
                egui::StrokeKind::Inside);
            p.text(rect.center(), Align2::CENTER_CENTER, note.text.as_str(),
                FontId::proportional(11.0), Color32::from_rgba_unmultiplied(
                    CREAM.r(), CREAM.g(), CREAM.b(), (255.0 * alpha) as u8));
        });
}

fn mix(a: Color32, b: Color32, fraction: f32) -> Color32 {
    let t = fraction.clamp(0.0, 1.0);
    let m = |x: u8, y: u8| ((x as f32 * (1.0 - t) + y as f32 * t).round()) as u8;
    Color32::from_rgb(m(a.r(), b.r()), m(a.g(), b.g()), m(a.b(), b.b()))
}

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
        ui.menu_button("App Updates", |ui| {
            if ui.button("Check for Updates...").clicked() {
                crate::cadcraft_android_wheel::check_cadcraft_updates();
                ui.close();
            }
            ui.label("Download & install within CADCraft");
        });
        ui.menu_button("Stylus Wheel", |ui| {
            if ui.checkbox(&mut app.ui.cad_wheel_enabled, "Stylus Wheel On").clicked() {
                if !app.ui.cad_wheel_enabled { app.ui.cad_wheel_open = false; }
                notify(ui.ctx(), if app.ui.cad_wheel_enabled {
                    "Wheel ON • hover + pen button" } else { "Wheel OFF" });
                ui.close();
            }
            if ui.button("Customize Wheel...").clicked() {
                app.ui.cad_wheel_customize = true;
                ui.close();
            }
            if ui.button("Reset to CAD Defaults").clicked() {
                app.ui.cad_wheel_actions = default_actions();
                app.ui.cad_wheel_size = DEFAULT_SIZE;
                app.ui.cad_wheel_opacity = DEFAULT_OPACITY;
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

fn wheel_index(pos: Pos2, center: Pos2, scale: f32) -> Option<usize> {
    let delta = pos - center;
    let distance = delta.length();
    if distance < HUB * scale || distance > RADIUS * scale { return None; }
    let step = FULL / SECTORS;
    let angle = (delta.y.atan2(delta.x) + std::f32::consts::FRAC_PI_2 + step / 2.0).rem_euclid(FULL);
    Some(((angle / step).floor() as usize).min(7))
}

fn draw_glyph(ui: &egui::Ui, action: &str, pos: Pos2, scale: f32) {
    use crate::icons::Icon;
    let icon = match action {
        "line" => Icon::Line, "pline" => Icon::Polyline, "circle" => Icon::Circle,
        "ui.panel.layers" => Icon::Layers, "pan" => Icon::Pan,
        "trim" => Icon::Trim, "undo" => Icon::Undo, "redo" => Icon::Redo,
        "osnap" => Icon::Point, "move" => Icon::Move, "erase" => Icon::Erase,
        "dist" => Icon::DimLinear, _ => Icon::Properties,
    };
    crate::icons::paint(ui.painter(), Rect::from_center_size(
        pos, Vec2::splat(24.0 * scale)), icon, false);
}

fn draw_ring(ui: &mut egui::Ui, center: Pos2, scale: f32, selected: Option<usize>,
    actions: &[String], opacity: f32)
{
    let painter = ui.painter();
    let radius = RADIUS * scale;
    // Identical compact 12-layer feathered shadow to PhotoCraft's approved
    // painter; no hard border or opaque concentric dark rings.
    for step in 0..12 {
        let spread = (12.0 - step as f32 * 0.82) * scale;
        let softness = 0.008 + step as f32 * 0.0017;
        painter.circle_filled(center + Vec2::new(0.8, 2.0) * scale,
            radius + spread, Color32::from_black_alpha(
                (255.0 * softness * opacity) as u8));
    }
    painter.circle_filled(center, radius, tinted(Color32::from_rgb(65, 65, 70), opacity));
    let sector = FULL / SECTORS;
    for k in 0..8 {
        let a = -std::f32::consts::FRAC_PI_2 + (k as f32) * sector;
        let begin = a - sector / 2.0 + 0.018;
        let end = a + sector / 2.0 - 0.018;
        let mut points = vec![center];
        for step in 0..=16 {
            let theta = begin + (end - begin) * step as f32 / 16.0;
            points.push(center + Vec2::new(theta.cos(), theta.sin()) * radius);
        }
        let normal = if k % 2 == 0 {
            mix(Color32::from_rgb(60, 60, 65), Color32::from_rgb(80, 80, 85), 0.18)
        } else {
            mix(Color32::from_rgb(60, 60, 65), Color32::from_rgb(80, 80, 85), 0.68)
        };
        let active = selected == Some(k);
        let fill = if active { mix(normal, BRAND, 0.76) } else { normal };
        painter.add(egui::Shape::convex_polygon(points, tinted(fill, opacity),
            Stroke::new(if active { 1.8 } else { 0.65 },
                if active { BRAND } else { tinted(Color32::from_gray(105), opacity * 0.7) })));
        let icon_pos = center + Vec2::new(a.cos(), a.sin()) * (87.0 * scale);
        let action = actions.get(k).map_or(DEFAULT_ACTIONS[k], String::as_str);
        draw_glyph(ui, action, icon_pos - Vec2::new(0.0, 10.0) * scale, scale);
        painter.text(icon_pos + Vec2::new(0.0, 13.0 * scale),
            Align2::CENTER_CENTER, label(action), FontId::proportional(11.0 * scale),
            tinted(Color32::from_rgb(208, 204, 207), opacity));
    }
    painter.circle_stroke(center, radius, Stroke::new(0.8, tinted(Color32::from_gray(115), opacity * 0.58)));
    // Solid pink Cc hub with the exact transparent cream vector glyph.
    painter.circle_filled(center, HUB * scale, tinted(BRAND, opacity));
    painter.circle_stroke(center, HUB * scale, Stroke::new(1.3, tinted(CREAM, opacity)));
    paint_center_glyph(ui, Rect::from_center_size(center - Vec2::new(0.0, 9.0) * scale,
        Vec2::splat(61.0 * scale)), opacity);
    let name = selected.and_then(|i| actions.get(i)).map(|id| label(id));
    painter.text(center + Vec2::new(0.0, 22.0) * scale, Align2::CENTER_CENTER,
        name.unwrap_or("Default"), FontId::proportional(11.0 * scale),
        tinted(Color32::WHITE, opacity));
}

fn preview_actual_size(app: &CadApp, ctx: &egui::Context, dialog: Rect) {
    let screen = ctx.content_rect();
    let size = WHEEL_SIZE * app.ui.cad_wheel_size;
    let margin = 16.0;
    let right_room = screen.right() - dialog.right();
    let left_room = dialog.left() - screen.left();
    let x = if right_room >= size + 2.0 * margin {
        (dialog.right() + screen.right()) * 0.5
    } else if left_room >= size + 2.0 * margin {
        (screen.left() + dialog.left()) * 0.5
    } else { screen.center().x };
    let center = Pos2::new(x.clamp(screen.left() + size / 2.0,
        (screen.right() - size / 2.0).max(screen.left() + size / 2.0)),
        dialog.center().y.clamp(screen.top() + size / 2.0,
        (screen.bottom() - size / 2.0).max(screen.top() + size / 2.0)));
    egui::Area::new(Id::new("cadcraft-wheel-actual-size-preview"))
        .order(egui::Order::Foreground)
        .fixed_pos(center - Vec2::splat(size / 2.0))
        .interactable(false)
        .show(ctx, |ui| {
            let (rect, _) = ui.allocate_exact_size(Vec2::splat(size), Sense::hover());
            draw_ring(ui, rect.center(), app.ui.cad_wheel_size,
                None, &app.ui.cad_wheel_actions, app.ui.cad_wheel_opacity);
        });
}

#[cfg(target_os = "android")]
pub fn check_cadcraft_updates() {
    cadcraft_android_updater_bridge::check_updates();
}

/// Drawn above the CAD canvas without an always-visible launcher. A validated
/// HONOR Magic-Pencil button event is the only normal path to open the wheel.
pub fn show(app: &mut CadApp, ctx: &egui::Context, _bounds: egui::Rect) {
    // NativeActivity consumes ONLY codes 19/20 from named Magic-Pencil devices.
    // Never interpret physical keyboard arrows as pen buttons.
    let device_scan_id = Id::new("cadcraft-wheel-device-last-scan");
    let refresh = ctx.data(|d| d.get_temp::<Instant>(device_scan_id))
        .is_none_or(|t| t.elapsed() >= Duration::from_secs(2));
    if refresh {
        let ids = cadcraft_android_updater_bridge::stylus_device_ids();
        android_activity::cad_stylus_configure(app.ui.cad_wheel_enabled, &ids);
        ctx.data_mut(|d| d.insert_temp(device_scan_id, Instant::now()));
    }
    for code in android_activity::cad_stylus_native_take() {
        if app.ui.cad_wheel_enabled && !app.ui.cad_wheel_customize && (code == 20 || code == 19) {
            app.ui.cad_wheel_open = !app.ui.cad_wheel_open;
            if app.ui.cad_wheel_open {
                let p = ctx.input(|i| i.pointer.hover_pos()).unwrap_or(ctx.content_rect().center());
                let screen = ctx.content_rect();
                let half = WHEEL_SIZE * app.ui.cad_wheel_size / 2.0 + 10.0;
                let center = Pos2::new(
                    p.x.clamp(screen.left() + half, (screen.right() - half).max(screen.left() + half)),
                    p.y.clamp(screen.top() + half, (screen.bottom() - half).max(screen.top() + half)));
                ctx.data_mut(|d| d.insert_temp(Id::new("cadcraft-wheel-center"), center));
                notify(ctx, "Hover to highlight • tap tip to select");
            } else {
                notify(ctx, "Wheel cancelled");
            }
        }
    }

    if app.ui.cad_wheel_customize {
        app.ui.cad_wheel_open = false;
        let mut open = true;
        let response = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("cadcraft_android_wheel_customize"))
            .open(&mut open).resizable(false).collapsible(false)
            .default_width(320.0)
            .show(ctx, |ui| {
                ui.label("Style: Default  •  8 segments");
                ui.label("Choose a CAD command for each position. Existing selections swap.");
                ui.separator();
                for idx in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", idx + 1));
                        let current = app.ui.cad_wheel_actions.get(idx).cloned()
                            .unwrap_or_else(|| DEFAULT_ACTIONS[idx].to_owned());
                        let mut chosen = current.clone();
                        egui::ComboBox::from_id_salt(("cadcraft_wheel_slot", idx))
                            .selected_text(label(&current)).width(180.0)
                            .show_ui(ui, |ui| {
                                for (name, id) in ACTIONS {
                                    ui.selectable_value(&mut chosen, id.to_string(), name);
                                }
                            });
                        if chosen != current {
                            if let Some(previous) = app.ui.cad_wheel_actions.iter()
                                .position(|cmd| cmd == &chosen)
                            {
                                app.ui.cad_wheel_actions[previous] = current;
                            }
                            app.ui.cad_wheel_actions[idx] = chosen;
                        }
                    });
                }
                ui.separator();
                ui.scope(|ui| {
                    ui.visuals_mut().selection.bg_fill = BRAND;
                    ui.add(egui::Slider::new(&mut app.ui.cad_wheel_size, 0.75..=1.25)
                        .text("Wheel size").custom_formatter(|v, _| format!("{:.0}%", v * 100.0)));
                    ui.add(egui::Slider::new(&mut app.ui.cad_wheel_opacity, 0.60..=1.0)
                        .text("Opacity").custom_formatter(|v, _| format!("{:.0}%", v * 100.0)));
                });
                if ui.button("Restore Default").clicked() {
                    app.ui.cad_wheel_actions = default_actions();
                    app.ui.cad_wheel_size = DEFAULT_SIZE;
                    app.ui.cad_wheel_opacity = DEFAULT_OPACITY;
                    notify(ctx, "Stylus Wheel restored to Default");
                }
                ui.separator();
                ui.label("Actual-size preview appears beside this window.");
                ui.label("Pen button opens wheel • hover highlights • tip selects.");
            });
        app.ui.cad_wheel_customize = open;
        if let Some(result) = response {
            preview_actual_size(app, ctx, result.response.rect);
        }
    }
    show_feedback(ctx);
    if !app.ui.cad_wheel_enabled || !app.ui.cad_wheel_open || app.ui.cad_wheel_customize { return; }
    let center = ctx.data(|d| d.get_temp::<Pos2>(Id::new("cadcraft-wheel-center")))
        .unwrap_or_else(|| ctx.content_rect().center());
    let size = WHEEL_SIZE * app.ui.cad_wheel_size;
    let pos = center - Vec2::splat(size / 2.0);
    let mut chosen: Option<String> = None;
    egui::Area::new(Id::new("cadcraft_android_stylus_wheel"))
        .order(egui::Order::Foreground).fixed_pos(pos)
        .show(ctx, |ui| {
            let (rect, response) = ui.allocate_exact_size(Vec2::splat(size), Sense::click());
            let hover = ctx.input(|i| i.pointer.hover_pos());
            let highlighted = hover.and_then(|p| wheel_index(p, center, app.ui.cad_wheel_size));
            draw_ring(ui, rect.center(), app.ui.cad_wheel_size, highlighted,
                &app.ui.cad_wheel_actions, app.ui.cad_wheel_opacity);
            if response.clicked() {
                if let Some(at) = ctx.input(|i| i.pointer.interact_pos()) {
                    chosen = wheel_index(at, center, app.ui.cad_wheel_size)
                        .and_then(|i| app.ui.cad_wheel_actions.get(i).cloned());
                }
                app.ui.cad_wheel_open = false;
            }
        });
    if let Some(cmd) = chosen {
        if app.session.docs.is_empty() && !cmd.starts_with("ui.") {
            app.set_status("Create or open a drawing before using CAD tools.");
            notify(ctx, "Open a drawing before selecting a CAD command");
        } else {
            crate::menus::activate(app, &cmd);
            notify(ctx, "Wheel selection accepted");
        }
    }
}
