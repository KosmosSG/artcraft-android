//! LightCraft Android PhotoCraft-parity radial wheel.
//! Visual 8-segment overlay is NON-INTERACTIVE: only wheel-owned raw input
//! is consumed before egui hit-tests the canvas (avoids stylus hover bleed).
use egui::{Align2, Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, vec2};
use serde::{Deserialize, Serialize};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
const CYAN: Color32 = Color32::from_rgb(0, 180, 246);
const NAVY: Color32 = Color32::from_rgb(0, 45, 69);
const OPEN: &str = "lightcraft.android.wheel.open";
const SETTINGS: &str = "lightcraft.android.wheel.settings";
const CENTER: &str = "lightcraft.android.wheel.center";
const HOVER: &str = "lightcraft.android.wheel.hover";
const NOTIFY: &str = "lightcraft.android.wheel.notify";
const PEN: &str = "lightcraft.android.wheel.pen-hover";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum WheelAction {
    Edit, Crop, Mask, Remove, Picker, Zoom, Undo, Redo, Profiles,
    Versions, BeforeAfter, Fit, History, Compare,
}
impl WheelAction {
    const ALL: [Self; 14] = [
        Self::Edit, Self::Crop, Self::Mask, Self::Remove, Self::Picker, Self::Zoom,
        Self::Undo, Self::Redo, Self::Profiles, Self::Versions,
        Self::BeforeAfter, Self::Fit, Self::History, Self::Compare,
    ];
    pub fn label(self) -> &'static str {
        match self {
            Self::Edit => "Edit", Self::Crop => "Crop", Self::Mask => "Mask",
            Self::Remove => "Remove", Self::Picker => "Picker", Self::Zoom => "Zoom",
            Self::Undo => "Undo", Self::Redo => "Redo",
            Self::Profiles => "Profiles", Self::Versions => "Versions",
            Self::BeforeAfter => "Before/After", Self::Fit => "Fit",
            Self::History => "History", Self::Compare => "Compare",
        }
    }
    pub fn command(self) -> &'static str {
        match self {
            Self::Edit => "panel.edit", Self::Crop => "panel.crop",
            Self::Mask => "panel.masking", Self::Remove => "panel.remove",
            Self::Picker => "tool.wbPicker", Self::Zoom => "view.zoomToggle",
            Self::Undo => "edit.undo", Self::Redo => "edit.redo",
            Self::Profiles => "panel.profiles", Self::Versions => "panel.versions",
            Self::BeforeAfter => "view.beforeAfter", Self::Fit => "view.zoomFit",
            Self::History => "panel.activity", Self::Compare => "view.compare",
        }
    }
}
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default, rename_all = "camelCase")]
pub struct WheelPrefs {
    pub enabled: bool,
    pub size_percent: f32,
    pub opacity_percent: f32,
    pub soft_shadow: bool,
    pub slots: [WheelAction; 8],
}
impl Default for WheelPrefs {
    fn default() -> Self {
        Self {
            enabled: true, size_percent: 100.0, opacity_percent: 85.0,
            soft_shadow: true,
            // PhotoCraft placement: top, top-right, right, bottom-right,
            // bottom, bottom-left, left, top-left.
            slots: [
                WheelAction::Edit, WheelAction::Crop, WheelAction::Mask,
                WheelAction::Remove, WheelAction::Zoom, WheelAction::Picker,
                WheelAction::Redo, WheelAction::Undo,
            ],
        }
    }
}
fn scale(p: &WheelPrefs) -> f32 { p.size_percent.clamp(75.0, 125.0) / 100.0 }
fn mix(a: Color32, b: Color32, amount: f32) -> Color32 {
    let u = amount.clamp(0.0, 1.0);
    let blend = |x: u8, y: u8| (x as f32 * (1.0 - u) + y as f32 * u).round() as u8;
    Color32::from_rgb(blend(a.r(), b.r()), blend(a.g(), b.g()), blend(a.b(), b.b()))
}
fn hit(center: Pos2, pos: Pos2, p: &WheelPrefs) -> Option<usize> {
    let v = pos - center;
    let dist = v.length();
    if dist < INNER * scale(p) || dist > (R + 10.0) * scale(p) { return None; }
    let degrees = v.y.atan2(v.x).to_degrees();
    Some((((degrees + 112.5).rem_euclid(360.0) / 45.0).floor() as usize).min(7))
}
fn notify(ctx: &Context, message: &str) {
    let now = ctx.input(|i| i.time);
    ctx.data_mut(|d| d.insert_temp(Id::new(NOTIFY), (message.to_owned(), now)));
    ctx.request_repaint();
}
pub fn open_settings(ctx: &Context) {
    ctx.data_mut(|d| { d.insert_temp(Id::new(SETTINGS), true); d.insert_temp(Id::new(OPEN), false); });
    ctx.request_repaint();
}
pub fn request_stylus_toggle(ctx: &Context) {
    ctx.data_mut(|d| d.insert_temp(Id::new("lightcraft.android.wheel.toggle-request"), true));
    ctx.request_repaint();
}
pub fn set_pen_hover(ctx: &Context, position: Option<Pos2>) {
    let changed = ctx.data(|d| d.get_temp::<Option<Pos2>>(Id::new(PEN))).flatten() != position;
    if changed {
        ctx.data_mut(|d| d.insert_temp(Id::new(PEN), position));
        ctx.request_repaint();
    }
}

/// Captures ONLY events within the open wheel, before the normal canvas/UI
/// receives them. A single PointerGone clears a pre-existing canvas hover.
/// The visual wheel remains non-interactive, avoiding egui's previous-frame
/// hit-test leak into masked/crop controls when hovering.
pub fn capture(p: &WheelPrefs, ctx: &Context, raw: &mut RawInput) {
    if !p.enabled { return; }
    let open = ctx.data(|d| d.get_temp::<bool>(Id::new(OPEN))).unwrap_or(false);
    let settings = ctx.data(|d| d.get_temp::<bool>(Id::new(SETTINGS))).unwrap_or(false);
    if !open || settings { return; }
    let Some(center) = ctx.data(|d| d.get_temp::<Pos2>(Id::new(CENTER))) else { return; };
    let mut background_cleared = ctx.data(|d| d.get_temp::<bool>(Id::new("lc-wheel-cleared"))).unwrap_or(false);
    let mut output = Vec::with_capacity(raw.events.len());
    let mut chosen: Option<usize> = None;
    for event in std::mem::take(&mut raw.events) {
        let pointer = match &event {
            egui::Event::PointerMoved(pos) => Some(*pos),
            egui::Event::PointerButton { pos, .. } => Some(*pos),
            egui::Event::Touch { pos, .. } => Some(*pos),
            _ => None,
        };
        if let Some(pos) = pointer {
            if (pos - center).length() <= (R + 10.0) * scale(p) {
                ctx.data_mut(|d| d.insert_temp(Id::new(HOVER), Some(pos)));
                if !background_cleared {
                    output.push(egui::Event::PointerGone);
                    background_cleared = true;
                }
                match &event {
                    egui::Event::PointerButton { pressed: true, .. } => chosen = hit(center, pos, p),
                    egui::Event::Touch { phase: egui::TouchPhase::Start, .. } => chosen = hit(center, pos, p),
                    _ => {}
                }
                ctx.request_repaint();
                continue;
            }
            background_cleared = false;
            ctx.data_mut(|d| d.insert_temp::<Option<Pos2>>(Id::new(HOVER), None));
        }
        output.push(event);
    }
    raw.events = output;
    ctx.data_mut(|d| d.insert_temp(Id::new("lc-wheel-cleared"), background_cleared));
    if let Some(slot) = chosen {
        ctx.data_mut(|d| {
            d.insert_temp(Id::new("lightcraft.android.wheel.chosen"), Some(p.slots[slot]));
            d.insert_temp(Id::new(OPEN), false);
        });
        notify(ctx, "Wheel selection accepted");
    }
}
fn icon(p: &egui::Painter, c: Pos2, size: f32, act: WheelAction, color: Color32) {
    // Vector geometry rather than special font glyphs: no MagicOS tofu.
    let r = size * 0.45;
    let stroke = Stroke::new((size / 12.0).max(1.4), color);
    let seg = |a: egui::Vec2, b: egui::Vec2| p.line_segment([c + a, c + b], stroke);
    match act {
        WheelAction::Undo | WheelAction::Redo => {
            let reversed = act == WheelAction::Undo;
            let mut points = Vec::new();
            for j in 0..=16 {
                let t = (if reversed { 210.0 } else { -30.0 }) +
                    (if reversed { -1.0 } else { 1.0 }) * (j as f32 / 16.0) * 240.0;
                points.push(c + vec2(t.to_radians().cos(), t.to_radians().sin()) * r);
            }
            p.add(Shape::line(points, stroke));
            let x = if reversed { -r } else { r };
            seg(vec2(x, -0.10 * size), vec2(x + if reversed { r * 0.48 } else { -r * 0.48 }, -0.44 * size));
            seg(vec2(x, -0.10 * size), vec2(x + if reversed { r * 0.48 } else { -r * 0.48 }, r * 0.23));
        }
        WheelAction::Crop => {
            seg(vec2(-r, -r), vec2(-r, r * 0.58));
            seg(vec2(-r, -r), vec2(r * 0.56, -r));
            seg(vec2(r, r), vec2(-r * 0.56, r));
            seg(vec2(r, r), vec2(r, -r * 0.58));
        }
        WheelAction::Mask => {
            p.circle_stroke(c, r, stroke);
            p.circle_filled(c, r * 0.35, color);
        }
        WheelAction::Remove => {
            seg(vec2(-r * 0.65, -r * 0.65), vec2(r * 0.65, r * 0.65));
            seg(vec2(-r * 0.65, r * 0.65), vec2(r * 0.65, -r * 0.65));
            p.circle_stroke(c, r, Stroke::new(stroke.width * 0.6, color));
        }
        WheelAction::Picker => {
            seg(vec2(-r * 0.70, r * 0.85), vec2(r * 0.50, -r * 0.45));
            seg(vec2(r * 0.30, -r * 0.35), vec2(r * 0.70, -r * 0.75));
            seg(vec2(r * 0.52, -r), vec2(r, -r * 0.5));
            p.circle_stroke(c + vec2(-r * 0.76, r * 0.8), r * 0.22, stroke);
        }
        WheelAction::Zoom | WheelAction::Fit => {
            p.circle_stroke(c - vec2(r * 0.15, r * 0.15), r * 0.64, stroke);
            seg(vec2(r * 0.28, r * 0.31), vec2(r * 0.82, r * 0.86));
            if act == WheelAction::Zoom {
                seg(vec2(-r * 0.55, -r * 0.15), vec2(r * 0.25, -r * 0.15));
                seg(vec2(-r * 0.15, -r * 0.55), vec2(-r * 0.15, r * 0.25));
            }
        }
        WheelAction::Edit | WheelAction::Profiles | WheelAction::Versions |
        WheelAction::History | WheelAction::Compare | WheelAction::BeforeAfter => {
            for dy in [-r * 0.66, 0.0, r * 0.66] {
                seg(vec2(-r, dy), vec2(r, dy));
                p.circle_filled(c + vec2(if dy == 0.0 { -r * 0.35 } else { r * 0.38 }, dy),
                    r * 0.17, color);
            }
        }
    }
}
/// This renderer is used without resizing in the pop-out preview.
fn paint(ui: &mut Ui, p: &WheelPrefs, hover: Option<Pos2>) {
    let k = scale(p);
    let size = SIZE * k;
    let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
    let c = rect.center();
    let painter = ui.painter_at(rect);
    let alpha = p.opacity_percent.clamp(60.0, 100.0) / 100.0;
    if p.soft_shadow {
        for j in 0..12 {
            let spread = (12.0 - j as f32 * 0.82) * k;
            let strength = 0.008 + j as f32 * 0.0017;
            painter.circle_filled(c + vec2(0.8, 2.0) * k,
                R * k + spread, Color32::from_black_alpha((strength * 255.0) as u8));
        }
    }
    painter.circle_filled(c, R * k, Color32::from_gray(45).gamma_multiply(alpha));
    let active = hover.and_then(|pos| hit(c, pos, p));
    for slot in 0..8 {
        let degrees = -90.0 + slot as f32 * 45.0;
        let left = (degrees - 21.5).to_radians();
        let right = (degrees + 21.5).to_radians();
        let mut verts = vec![c];
        for j in 0..=16 {
            let a = left + (right - left) * (j as f32 / 16.0);
            verts.push(c + vec2(a.cos(), a.sin()) * R * k);
        }
        let hover = active == Some(slot);
        let normal = if slot % 2 == 0 { Color32::from_rgb(51, 53, 56) }
                     else { Color32::from_rgb(66, 68, 71) };
        let fill = if hover { mix(normal, CYAN, 0.70) } else { normal };
        painter.add(Shape::convex_polygon(verts, fill.gamma_multiply(alpha),
            Stroke::new(if hover { 1.5 } else { 0.65 },
                if hover { CYAN } else { Color32::from_gray(85) })));
        let a = degrees.to_radians();
        let at = c + vec2(a.cos(), a.sin()) * 87.0 * k;
        icon(&painter, at - vec2(0.0, 10.0) * k, 23.0 * k, p.slots[slot], Color32::from_rgb(225, 231, 235));
        painter.text(at + vec2(0.0, 13.0) * k, Align2::CENTER_CENTER,
            p.slots[slot].label(), FontId::proportional(11.0 * k), Color32::from_gray(185));
    }
    painter.circle_stroke(c, R * k, Stroke::new(0.8, Color32::from_gray(95)));
    painter.circle_filled(c, (INNER + 2.0) * k, NAVY);
    painter.circle_stroke(c, (INNER + 2.0) * k, Stroke::new(1.4, CYAN));
    // Preserve the exact LightCraft icon from the app's launcher/menu.
    let pic = egui::Image::from_bytes("bytes://lightcraft/wheel/lc.png", include_bytes!("menus/lc-menu.png"))
        .fit_to_exact_size(vec2(39.0, 39.0) * k);
    ui.put(egui::Rect::from_center_size(c - vec2(0.0, 8.0) * k, vec2(39.0, 39.0) * k), pic);
    painter.text(c + vec2(0.0, 22.0) * k, Align2::CENTER_CENTER,
        active.map(|idx| p.slots[idx].label()).unwrap_or("Default"),
        FontId::proportional(11.0 * k), Color32::WHITE);
}
fn preview(ctx: &Context, p: &WheelPrefs, dialog: egui::Rect) {
    let screen = ctx.content_rect();
    let size = SIZE * scale(p);
    let margin = 16.0;
    let x = if screen.right() - dialog.right() >= size + 2.0 * margin {
        (dialog.right() + screen.right()) * 0.5
    } else if dialog.left() - screen.left() >= size + 2.0 * margin {
        (dialog.left() + screen.left()) * 0.5
    } else { screen.center().x };
    let center = egui::pos2(
        x.clamp(screen.left() + size * 0.5, (screen.right() - size * 0.5).max(screen.left() + size * 0.5)),
        dialog.center().y.clamp(screen.top() + size * 0.5,
            (screen.bottom() - size * 0.5).max(screen.top() + size * 0.5)),
    );
    egui::Area::new(Id::new("lightcraft.android.wheel.preview"))
        .order(Order::Foreground).interactable(false)
        .fixed_pos(center - vec2(size * 0.5, size * 0.5))
        .show(ctx, |ui| paint(ui, p, None));
}
fn bottom_bar(ctx: &Context) {
    let Some((text, start)) = ctx.data(|d| d.get_temp::<(String, f64)>(Id::new(NOTIFY))) else { return; };
    let age = ctx.input(|i| i.time) - start;
    if !(0.0..2.4).contains(&age) { return; }
    let a = if age <= 1.9 { 1.0 } else { (1.0 - (age - 1.9) / 0.5).clamp(0.0, 1.0) };
    if age > 1.9 { ctx.request_repaint_after(std::time::Duration::from_millis(40)); }
    let screen = ctx.content_rect();
    egui::Area::new(Id::new("lightcraft.android.wheel.bottom"))
        .order(Order::Tooltip)
        .fixed_pos(egui::pos2(screen.center().x - 175.0, screen.bottom() - 43.0))
        .interactable(false).show(ctx, |ui| {
            let (rect, _) = ui.allocate_exact_size(vec2(350.0, 31.0), Sense::hover());
            let painter = ui.painter_at(rect);
            painter.rect_filled(rect, 13.0, Color32::from_black_alpha((215.0 * a) as u8));
            painter.rect_stroke(rect, 13.0,
                Stroke::new(1.0, Color32::from_gray(90).gamma_multiply(a as f32)),
                StrokeKind::Inside);
            painter.text(rect.center(), Align2::CENTER_CENTER, text,
                FontId::proportional(11.0), Color32::WHITE.gamma_multiply(a as f32));
        });
}
fn pointer(ctx: &Context) {
    let Some(pos) = ctx.data(|d| d.get_temp::<Option<Pos2>>(Id::new(PEN))).flatten() else { return; };
    let painter = ctx.layer_painter(egui::LayerId::new(Order::Tooltip, Id::new("lightcraft.android.pen.cursor")));
    painter.circle_stroke(pos, 7.0, Stroke::new(1.8, CYAN));
    painter.circle_filled(pos, 1.3, CYAN);
}
pub fn show(app: &mut crate::LightcraftApp, ctx: &Context) {
    let mut prefs = app.ui.settings.stylus_wheel.clone();
    let mut open = ctx.data(|d| d.get_temp::<bool>(Id::new(OPEN))).unwrap_or(false);
    let mut settings = ctx.data(|d| d.get_temp::<bool>(Id::new(SETTINGS))).unwrap_or(false);
    let toggle = ctx.data_mut(|d| {
        let b = d.get_temp::<bool>(Id::new("lightcraft.android.wheel.toggle-request")).unwrap_or(false);
        d.insert_temp(Id::new("lightcraft.android.wheel.toggle-request"), false);
        b
    });
    if toggle && prefs.enabled {
        open = !open;
        let screen = ctx.content_rect();
        let radius = R * scale(&prefs) + 16.0;
        let pointer = ctx.data(|d| d.get_temp::<Option<Pos2>>(Id::new(PEN))).flatten()
            .or_else(|| ctx.input(|i| i.pointer.hover_pos()));
        let pos = pointer.unwrap_or_else(|| screen.center());
        let center = egui::pos2(pos.x.clamp(screen.left() + radius, screen.right() - radius),
            pos.y.clamp(screen.top() + radius, screen.bottom() - radius));
        ctx.data_mut(|d| { d.insert_temp(Id::new(CENTER), center); d.insert_temp(Id::new(HOVER), None::<Pos2>); });
        notify(ctx, if open { "Hover to highlight • tap tip to select" } else { "Wheel closed" });
    }
    let chosen = ctx.data_mut(|d| {
        let a = d.get_temp::<Option<WheelAction>>(Id::new("lightcraft.android.wheel.chosen")).flatten();
        d.insert_temp(Id::new("lightcraft.android.wheel.chosen"), None::<WheelAction>);
        a
    });
    if let Some(a) = chosen {
        if let Err(e) = app.run(a.command(), serde_json::Value::Null) {
            app.toast(ctx, e);
        }
    }
    if !prefs.enabled { open = false; }

    // PhotoCraft-style shortcut pad stays available but never pre-opens the wheel.
    if prefs.enabled && !settings {
        egui::Area::new(Id::new("lightcraft.android.wheel.pad"))
            .anchor(Align2::RIGHT_CENTER, vec2(-10.0, 0.0))
            .order(Order::Foreground).show(ctx, |ui| {
                ui.vertical(|ui| {
                    for (label, act) in [
                        ("Undo", Some(WheelAction::Undo)),
                        ("Redo", Some(WheelAction::Redo)),
                        ("Lc", None),
                        ("Zoom", Some(WheelAction::Zoom)),
                        ("Fit", Some(WheelAction::Fit)),
                    ] {
                        if ui.add_sized([52.0, if act.is_some() { 47.0 } else { 54.0 }],
                            egui::Button::new(egui::RichText::new(label)
                                .color(if act.is_none() { CYAN } else { Color32::WHITE }))).clicked() {
                            match act {
                                Some(a) => { if let Err(e) = app.run(a.command(), serde_json::Value::Null) {
                                    app.toast(ctx, e);
                                } }
                                None => request_stylus_toggle(ctx),
                            }
                        }
                    }
                });
            });
    }
    if settings {
        open = false;
        egui_extras::install_image_loaders(ctx);
        let mut dialog_open = true;
        let response = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("lightcraft.android.wheel.settings.window"))
            .default_width(320.0).resizable(false).collapsible(false)
            .open(&mut dialog_open).show(ctx, |ui| {
                ui.label("Style: Default  •  8 segments");
                ui.label("Choose a tool for each position. Existing selections swap positions.");
                ui.separator();
                for idx in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", idx + 1));
                        let old = prefs.slots[idx];
                        let mut wanted = old;
                        egui::ComboBox::from_id_salt(("lightcraft-wheel", idx))
                            .selected_text(old.label()).width(180.0).show_ui(ui, |ui| {
                                for action in WheelAction::ALL {
                                    ui.selectable_value(&mut wanted, action, action.label());
                                }
                            });
                        if wanted != old {
                            if let Some(other) = prefs.slots.iter().position(|a| *a == wanted) {
                                prefs.slots[other] = old;
                            }
                            prefs.slots[idx] = wanted;
                        }
                    });
                }
                ui.separator();
                ui.add(egui::Slider::new(&mut prefs.size_percent, 75.0..=125.0).text("Wheel size").suffix("%"));
                ui.add(egui::Slider::new(&mut prefs.opacity_percent, 60.0..=100.0).text("Opacity").suffix("%"));
                if ui.button("Restore Default").clicked() { prefs = WheelPrefs::default(); }
                ui.separator();
                ui.small("Actual-size preview appears beside this dialog.");
                ui.small("Pen hover + button opens wheel; tap tip to select.");
            });
        settings = dialog_open;
        if let Some(response) = response { preview(ctx, &prefs, response.response.rect); }
    } else if open {
        egui_extras::install_image_loaders(ctx);
        if let Some(center) = ctx.data(|d| d.get_temp::<Pos2>(Id::new(CENTER))) {
            let k = scale(&prefs);
            let size = SIZE * k;
            let pos = center - vec2(size * 0.5, size * 0.5);
            let hover = ctx.data(|d| d.get_temp::<Option<Pos2>>(Id::new(HOVER))).flatten();
            egui::Area::new(Id::new("lightcraft.android.wheel.overlay"))
                .order(Order::Foreground).interactable(false)
                .fixed_pos(pos).show(ctx, |ui| paint(ui, &prefs, hover));
        }
        if ctx.input(|i| i.key_pressed(egui::Key::Escape)) { open = false; }
    }
    if !open && !settings { pointer(ctx); }
    bottom_bar(ctx);
    app.ui.settings.stylus_wheel = prefs;
    ctx.data_mut(|d| { d.insert_temp(Id::new(OPEN), open); d.insert_temp(Id::new(SETTINGS), settings); });
}
