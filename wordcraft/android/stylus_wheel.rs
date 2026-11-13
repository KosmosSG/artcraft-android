//! WC_BLUE_STYLUS_WHEEL_V1: isolated PhotoCraft-style WordCraft radial input.
//! The wheel consumes its own raw stylus/mouse/touch input before the document.
//! No upstream editor source is modified and no hidden commands are synthesized.
use eframe::egui::{self, Color32, FontId, Pos2, Rect, Stroke, Vec2};
use serde_json::{json, Value};
use std::f32::consts::{PI, TAU};

/// All commands are official WordCraft v0.17 ribbon or edit command IDs.
/// Text selection is preserved by routing "Select" to the Draw tab's select tool.
pub const CHOICES: [(&str, &str); 13] = [
    ("Pen", "draw.pen"),
    ("Eraser", "draw.eraser"),
    ("Highlight", "draw.highlighter"),
    ("Select", "draw.select"),
    ("Copy", "edit.copy"),
    ("Paste", "edit.paste"),
    ("Undo", "edit.undo"),
    ("Redo", "edit.redo"),
    ("Bold", "format.bold"),
    ("Italic", "format.italic"),
    ("Save", "file.save"),
    ("Pencil", "draw.pencil"),
    ("Lasso", "draw.lasso"),
];
const DEFAULT: [usize; 8] = [0, 1, 4, 5, 3, 2, 6, 7];
const CYAN: Color32 = Color32::from_rgb(122, 216, 252);
const HUB: Color32 = Color32::from_rgb(14, 82, 165);

pub struct Wheel {
    pub enabled: bool,
    pub visible: bool,
    pen_hover: Option<Pos2>,
    center_override: Option<Pos2>,
    pub settings_open: bool,
    pub size: f32,
    pub opacity: f32,
    pub slots: [usize; 8],
    pub hovered: Option<usize>,
    pub active: usize,
    mouse_down: Option<usize>,
    touch_down: Option<(u64, u64, usize)>,
    owned_mouse: bool,
    pub pending: Option<usize>,
    last_command_at: Option<std::time::Instant>,
}

impl Wheel {
    pub fn load(saved: Option<&str>) -> Self {
        let mut wheel = Self {
            enabled: true,
            visible: false,
            pen_hover: None,
            center_override: None,
            settings_open: false,
            size: 284.0,
            opacity: 0.82,
            slots: DEFAULT,
            hovered: None,
            active: 0,
            mouse_down: None,
            touch_down: None,
            owned_mouse: false,
            pending: None,
            last_command_at: None,
        };
        if let Some(value) = saved.and_then(|s| serde_json::from_str::<Value>(s).ok()) {
            // Android.2 stored visible=true as its only ON switch.
            // Migrate it to enabled, never leave an always-on overlay open.
            wheel.enabled = value["enabled"].as_bool()
                .or_else(|| value["visible"].as_bool()).unwrap_or(true);
            if let Some(v) = value["size"].as_f64().filter(|v| v.is_finite()) {
                wheel.size = (v as f32).clamp(170.0, 380.0);
            }
            if let Some(v) = value["opacity"].as_f64().filter(|v| v.is_finite()) {
                wheel.opacity = (v as f32).clamp(0.25, 1.0);
            }
            if let Some(items) = value["slots"].as_array() {
                for (i, item) in items.iter().take(8).enumerate() {
                    if let Some(n) = item.as_u64().filter(|n| (*n as usize) < CHOICES.len()) {
                        wheel.slots[i] = n as usize;
                    }
                }
            }
        }
        wheel
    }

    pub fn config_json(&self) -> String {
        json!({"enabled":self.enabled, "size":self.size, "opacity":self.opacity,
               "slots":self.slots}).to_string()
    }

    pub fn reset(&mut self) {
        self.size = 284.0;
        self.opacity = 0.82;
        self.slots = DEFAULT;
        self.visible = false;
    }

    pub fn toggle_enabled(&mut self) {
        self.enabled = !self.enabled;
        self.visible = false;
        self.hovered = None;
        self.pending = None;
    }

    pub fn set_pen_hover(&mut self, at: Option<Pos2>) {
        self.pen_hover = at.filter(|p| p.x.is_finite() && p.y.is_finite());
    }

    pub fn open_at_hover(&mut self, ctx: &egui::Context) {
        if !self.enabled || self.settings_open { return; }
        let fallback = ctx.content_rect().center();
        self.center_override = self.pen_hover
            .or_else(|| ctx.input(|i| i.pointer.hover_pos()))
            .or(Some(fallback));
        self.visible = true;
        self.hovered = None;
        ctx.request_repaint();
    }

    pub fn pen_button(&mut self, ctx: &egui::Context) {
        if !self.enabled || self.settings_open { return; }
        if self.visible { self.visible = false; self.hovered = None; }
        else { self.open_at_hover(ctx); }
        ctx.request_repaint();
    }

    pub fn center(&self, screen: Rect) -> Pos2 {
        let radius = self.size * 0.5;
        let preferred = self.center_override.unwrap_or_else(||
            egui::pos2(screen.right() - radius - 92.0, screen.bottom() - radius - 92.0));
        egui::pos2(
            preferred.x.clamp(screen.left() + radius + 8.0,
                (screen.right() - radius - 8.0).max(screen.left() + radius + 8.0)),
            preferred.y.clamp(screen.top() + radius + 8.0,
                (screen.bottom() - radius - 8.0).max(screen.top() + radius + 8.0)),
        )
    }

    pub fn owns(&self, pos: Pos2, screen: Rect) -> bool {
        self.visible && pos.distance_sq(self.center(screen)) <= (self.size * 0.5 + 5.0).powi(2)
    }

    fn sector(&self, pos: Pos2, screen: Rect) -> Option<usize> {
        if !self.owns(pos, screen) { return None; }
        let c = self.center(screen);
        if pos.distance(c) <= self.size * 0.185 { return None; }
        // Wedges start at the top and proceed clockwise.
        let angle = ((pos.y - c.y).atan2(pos.x - c.x) + PI * 0.5).rem_euclid(TAU);
        Some(((angle / (TAU / 8.0)).floor() as usize).min(7))
    }

    fn queue(&mut self, slot: usize) {
        let now = std::time::Instant::now();
        if self.last_command_at.is_some_and(|previous|
            now.duration_since(previous) < std::time::Duration::from_millis(130)) {
            return; // Android may synthesize both Touch and PointerButton for one contact.
        }
        self.active = slot;
        self.pending = Some(self.slots[slot]);
        self.last_command_at = Some(now);
    }

    /// WC_WHEEL_MODAL_ISOLATION_V2: while open, pen hover, tap, drag and scroll
    /// are owned by the wheel. No document selection can occur underneath.
    /// Keyboard/IME commands pass through unmodified.
    pub fn filter_input(&mut self, raw: &mut egui::RawInput, screen: Rect) {
        if !self.visible { return; }
        let mut safe_events = Vec::with_capacity(raw.events.len() + 1);
        let mut saw_pointer = false;
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerMoved(pos) => {
                    saw_pointer = true;
                    self.hovered = self.sector(pos, screen);
                }
                egui::Event::PointerButton { pos, pressed, button, .. } => {
                    saw_pointer = true;
                    if button == egui::PointerButton::Primary {
                        if pressed {
                            self.owned_mouse = true;
                            self.mouse_down = self.sector(pos, screen);
                            if self.mouse_down.is_none() { self.visible = false; }
                        } else if self.owned_mouse {
                            if let (Some(a), Some(b)) = (self.mouse_down.take(), self.sector(pos, screen)) {
                                if a == b { self.queue(a); self.visible = false; }
                            }
                            self.owned_mouse = false;
                        }
                    } else if pressed { self.visible = false; }
                }
                egui::Event::Touch { device_id, id, phase, pos, .. } => {
                    saw_pointer = true;
                    match phase {
                        egui::TouchPhase::Start => {
                            if let Some(slot) = self.sector(pos, screen) {
                                self.touch_down = Some((device_id.0, id.0, slot));
                            } else { self.visible = false; }
                        }
                        egui::TouchPhase::End => {
                            if let Some((dev, tid, start)) = self.touch_down {
                                if dev == device_id.0 && tid == id.0 {
                                    if self.sector(pos, screen) == Some(start) {
                                        self.queue(start);
                                        self.visible = false;
                                    }
                                    self.touch_down = None;
                                }
                            }
                        }
                        egui::TouchPhase::Cancel => { self.touch_down = None; }
                        egui::TouchPhase::Move => { self.hovered = self.sector(pos, screen); }
                    }
                }
                egui::Event::MouseWheel { .. } | egui::Event::Zoom(_) => {}
                egui::Event::PointerGone => { self.hovered = None; }
                other => safe_events.push(other),
            }
        }
        if saw_pointer { safe_events.push(egui::Event::PointerGone); }
        raw.events = safe_events;
    }


    /// WC_APPROVED_WC_LAUNCHER_GLYPH_V1: actual approved art, not a font.
    fn wc_mark(ctx: &egui::Context) -> egui::TextureHandle {
        let id = egui::Id::new("wc-approved-launcher-glyph-v1");
        if let Some(existing) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
            return existing;
        }
        const RGBA: &[u8] = include_bytes!("stylus_wheel_wc.rgba");
        let image = egui::ColorImage::from_rgba_unmultiplied([192, 88], RGBA);
        let texture = ctx.load_texture("wordcraft-wheel-approved-Wc", image,
            egui::TextureOptions::LINEAR);
        ctx.data_mut(|d| d.insert_temp(id, texture.clone()));
        texture
    }

    /// Draw supported vector strokes; avoid Unicode symbols that render as
    /// boxes on Android/egui and share PhotoCraft's refined outline treatment.
    fn paint_icon(painter: &egui::Painter, at: Pos2, label: &str, unit: f32) {
        let st = Stroke::new(2.0 * unit, Color32::WHITE);
        let p = |x: f32, y: f32| at + egui::vec2(x * unit, y * unit);
        match label {
            "Undo" | "Redo" => {
                // WC_ANDROID4_REFINED_HISTORY_ARROWS_V1:
                // PhotoCraft-style U-turn with a real open arrow head.
                // Undo turns left, Redo mirrors horizontally (not arch glyphs).
                let dir = if label == "Undo" { 1.0 } else { -1.0 };
                let x = |v: f32| dir * v;
                let mut path = vec![p(x(-10.0), -3.5), p(x(1.0), -3.5)];
                for i in 1..=20 {
                    let t = i as f32 / 20.0;
                    let v = 1.0 - t;
                    let px = v*v*v*1.0 + 3.0*v*v*t*10.5
                        + 3.0*v*t*t*10.0 + t*t*t*2.5;
                    let py = v*v*v*(-3.5) + 3.0*v*v*t*(-3.5)
                        + 3.0*v*t*t*10.0 + t*t*t*9.5;
                    path.push(p(x(px), py));
                }
                painter.add(egui::Shape::line(path, st));
                painter.line_segment([p(x(-10.0),-3.5), p(x(-4.5),-9.0)],st);
                painter.line_segment([p(x(-10.0),-3.5), p(x(-4.5),2.0)],st);
            }
            "Pen" | "Pencil" | "Highlight" => {
                painter.add(egui::Shape::line(vec![
                    p(-9.0,9.0),p(-6.0,1.5),p(5.5,-10.0),p(10.0,-5.5),
                    p(-1.5,6.0),p(-9.0,9.0)
                ],st));
                painter.line_segment([p(-5.5,1.0),p(-1.5,5.0)],st);
                if label == "Highlight" {
                    painter.line_segment([p(-11.0,11.0),p(11.0,11.0)],st);
                }
            }
            "Eraser" => {
                painter.add(egui::Shape::line(vec![
                    p(-10.0,4.0),p(1.0,-9.0),p(10.0,-1.0),p(-1.0,11.0),p(-10.0,4.0)
                ],st));
                painter.line_segment([p(-5.0,-2.0),p(4.0,6.0)],st);
            }
            "Copy" | "Paste" => {
                let back = egui::Rect::from_min_max(p(-9.0,-10.0),p(5.0,6.0));
                let front = egui::Rect::from_min_max(p(-4.0,-5.0),p(10.0,11.0));
                painter.rect_stroke(back,1.0*unit,st,egui::StrokeKind::Inside);
                painter.rect_stroke(front,1.0*unit,st,egui::StrokeKind::Inside);
            }
            "Select" => {
                painter.circle_stroke(at,8.0*unit,st);
                painter.line_segment([p(-13.0,0.0),p(-5.0,0.0)],st);
                painter.line_segment([p(5.0,0.0),p(13.0,0.0)],st);
                painter.line_segment([p(0.0,-13.0),p(0.0,-5.0)],st);
                painter.line_segment([p(0.0,5.0),p(0.0,13.0)],st);
            }
            "Save" => {
                painter.rect_stroke(egui::Rect::from_min_max(p(-9.0,-10.0),p(9.0,10.0)),
                    2.0*unit,st,egui::StrokeKind::Inside);
                painter.line_segment([p(-5.0,-8.0),p(5.0,-8.0)],st);
                painter.line_segment([p(-5.0,4.0),p(5.0,4.0)],st);
            }
            "Lasso" => {
                painter.circle_stroke(p(-1.0,-2.0),8.0*unit,st);
                painter.line_segment([p(4.0,5.0),p(10.0,11.0)],st);
            }
            "Bold" | "Italic" => {
                painter.text(at,egui::Align2::CENTER_CENTER,
                    if label=="Bold"{"B"}else{"I"},
                    FontId::proportional(24.0*unit), Color32::WHITE);
            }
            _ => { painter.circle_stroke(at,6.0*unit,st); }
        }
    }

    // WC_ANDROID4_VISIBLE_SETTINGS_SLIDERS_V1: custom painted controls are
    // guaranteed visible with both light and dark themes on MagicOS.
    // The size/opacity values are the actual live wheel dimensions and alpha.
    fn bar_slider(ui: &mut egui::Ui, value: &mut f32,
                  min: f32, max: f32, width: f32) -> bool {
        let (rect, response) = ui.allocate_exact_size(
            egui::vec2(width, 24.0), egui::Sense::click_and_drag());
        let mut changed = false;
        if (response.clicked() || response.dragged())
            && response.interact_pointer_pos().is_some()
        {
            if let Some(at) = response.interact_pointer_pos() {
                let fraction = ((at.x - rect.left() - 9.0) / (rect.width() - 18.0))
                    .clamp(0.0, 1.0);
                let next = min + fraction * (max - min);
                if (next - *value).abs() > 0.0001 {
                    *value = next;
                    changed = true;
                }
            }
        }
        let track = Rect::from_center_size(rect.center(),
            egui::vec2((width - 18.0).max(8.0), 6.0));
        let fraction = ((*value - min) / (max - min)).clamp(0.0, 1.0);
        let x = track.left() + fraction * track.width();
        ui.painter().rect_filled(track, 3.0,
            Color32::from_rgb(171, 183, 198));
        if x > track.left() {
            let fill = Rect::from_min_max(track.left_top(),
                egui::pos2(x, track.bottom()));
            ui.painter().rect_filled(fill, 3.0,
                Color32::from_rgb(29, 117, 222));
        }
        ui.painter().circle_filled(egui::pos2(x, rect.center().y),
            7.0, CYAN);
        ui.painter().circle_stroke(egui::pos2(x, rect.center().y),
            7.0, Stroke::new(1.4, HUB));
        changed
    }

    /// Render the same wheel function in the live canvas and settings preview.
    /// No screenshot thumbnail scaling: size and opacity are both real values.
    pub fn paint(&self, ctx: &egui::Context, painter: &egui::Painter, center: Pos2, size: f32, opacity: f32,
                 selected: Option<usize>) {
        let radius = size * 0.5;
        // WC_ANDROID7_SOFT_FEATHER_SHADOW_V1: use sixteen fine, translucent
        // rings rather than the four coarse bands that appeared hard on
        // white document pages. Similar total darkness but a gentle radial
        // falloff, with only a slight downward offset. This same painter
        // drives the full-size settings preview. Leave cyan rim untouched.
        for step in 0..16 {
            let feather = 14.0 - step as f32 * 0.8;
            let alpha = if step < 10 { 1 } else { 2 };
            painter.circle_filled(center + egui::vec2(0.6, 1.4),
                radius + feather, Color32::from_black_alpha(alpha));
        }
        let sector_width = TAU / 8.0;
        for i in 0..8 {
            let begin = -PI * 0.5 + i as f32 * sector_width;
            let end = begin + sector_width;
            let mut points = Vec::with_capacity(24);
            for j in 0..=12 {
                let a = begin + (end - begin) * (j as f32 / 12.0);
                points.push(center + egui::vec2(a.cos(), a.sin()) * radius);
            }
            for j in (0..=8).rev() {
                let a = begin + (end - begin) * (j as f32 / 8.0);
                points.push(center + egui::vec2(a.cos(), a.sin()) * radius * 0.37);
            }
            let highlighted = selected == Some(i);
            let background = if highlighted {
                Color32::from_rgba_unmultiplied(9, 113, 212, (opacity * 244.0) as u8)
            } else {
                Color32::from_rgba_unmultiplied(65, 68, 73, (opacity * 245.0) as u8)
            };
            painter.add(egui::Shape::convex_polygon(
                points, background, Stroke::new(if highlighted {2.1} else {0.75},
                    if highlighted { CYAN } else { Color32::from_gray(89) })));
            let angle = (begin + end) * 0.5;
            let icon_pos = center + egui::vec2(angle.cos(), angle.sin()) * radius * 0.72
                + egui::vec2(0.0, -size * 0.025);
            let label = CHOICES[self.slots[i]].0;
            Self::paint_icon(painter, icon_pos, label, (size / 284.0).clamp(0.75, 1.35));
            painter.text(icon_pos + egui::vec2(0.0, size * 0.086),
                egui::Align2::CENTER_CENTER, label,
                FontId::proportional((size * 0.047).clamp(9.0, 16.0)),
                Color32::from_rgb(225, 231, 240));
        }
        // PhotoCraft hub ratio: inner radius 46 / outer radius 128 = 0.359.
        // Use 0.37 here, rather than Android.2's visibly undersized 0.235.
        painter.circle_filled(center, radius * 0.37, HUB);
        painter.circle_stroke(center, radius * 0.37, Stroke::new(1.6, CYAN));
        let logo = Self::wc_mark(ctx);
        let logo_rect = Rect::from_center_size(center - egui::vec2(0.0, size * 0.034),
            egui::vec2(size * 0.212, size * 0.098));
        painter.image(logo.id(), logo_rect, Rect::from_min_max(
            egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0)), Color32::WHITE);
        painter.text(center + egui::vec2(0.0, size * 0.106), egui::Align2::CENTER_CENTER,
            if self.visible { CHOICES[self.slots[self.active]].0 } else { "Default" },
            FontId::proportional((size * 0.039).clamp(10.0, 13.0)), Color32::WHITE);
        // WC_ANDROID6_APPROVED_CYAN_OUTER_RING_V1: outline the *outer circle*
        // only in the exact launcher Wc glyph cyan (#7AD8FC). Keep the
        // PhotoCraft-style soft shadow, eight dark segments, their fine
        // neutral dividers, and the central hub unchanged.
        painter.circle_stroke(center, radius, Stroke::new(1.5, CYAN));
    }

    pub fn show(&mut self, ctx: &egui::Context) -> bool {
        let mut changed = false;
        let screen = ctx.content_rect();
        if self.visible && !self.settings_open {
            let at = self.center(screen) - Vec2::splat(self.size / 2.0);
            egui::Area::new(egui::Id::new("wc_stylus_wheel_area"))
                .order(egui::Order::Foreground)
                .interactable(false)
                .fixed_pos(at)
                .show(ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(Vec2::splat(self.size), egui::Sense::hover());
                    // Android native stylus hover lives outside egui PointerMoved;
                    // prefer its actual pen position for highlight selection.
                    let highlighted = self.pen_hover.and_then(|p|
                        self.sector(p, screen)).or(self.hovered);
                    self.paint(ui.ctx(), ui.painter(), rect.center(),
                        self.size, self.opacity, highlighted);
                });
        }
        if let Some(at) = self.pen_hover {
            // Genuine stylus-hover indicator; no synthetic pointer contact.
            let painter = ctx.layer_painter(egui::LayerId::new(
                egui::Order::Tooltip, egui::Id::new("wc-pen-hover-indicator")));
            painter.circle_stroke(at, 6.0, Stroke::new(1.7, CYAN));
            painter.circle_filled(at, 1.7, CYAN);
            ctx.request_repaint_after(std::time::Duration::from_millis(60));
        }
        if self.settings_open {
            let mut open = true;
            egui::Window::new("WordCraft Stylus Wheel Customization")
                .id(egui::Id::new("wc_stylus_wheel_settings"))
                .open(&mut open)
                .default_width(450.0)
                .default_pos(egui::pos2(screen.left() + 28.0, screen.top() + 80.0))
                .show(ctx, |ui| {
                    ui.set_min_width(410.0);
                    ui.label("Default • WordCraft blue/cyan • PhotoCraft layout");
                    ui.separator();
                    // Align both labels and values in matching columns.
                    ui.horizontal(|ui| {
                        ui.add_sized([112.0, 24.0], egui::Label::new("Wheel size"));
                        changed |= Self::bar_slider(ui, &mut self.size, 170.0, 380.0, 190.0);
                        ui.add_sized([70.0, 24.0], egui::Label::new(
                            format!("{:.0} pt", self.size)));
                    });
                    ui.horizontal(|ui| {
                        ui.add_sized([112.0, 24.0], egui::Label::new("Wheel opacity"));
                        changed |= Self::bar_slider(ui, &mut self.opacity, 0.25, 1.0, 190.0);
                        ui.add_sized([70.0, 24.0], egui::Label::new(
                            format!("{:.0}%", self.opacity * 100.0)));
                    });
                    ui.small("Drag the cyan handle • the preview updates at actual size.");
                    ui.separator();
                    ui.label("Live preview (same geometry and opacity as on the canvas)");
                    egui::ScrollArea::horizontal().max_height(402.0).show(ui, |ui| {
                        let (rect, _) = ui.allocate_exact_size(Vec2::splat(self.size + 30.0),
                            egui::Sense::hover());
                        self.paint(ui.ctx(), ui.painter(), rect.center(), self.size, self.opacity, Some(self.active));
                    });
                    ui.separator();
                    ui.label("Edit shortcuts • each slot can be assigned independently");
                    for row in 0..4 {
                        ui.horizontal(|ui| {
                            for col in 0..2 {
                                let slot = row * 2 + col;
                                let mut selected = self.slots[slot];
                                egui::ComboBox::from_id_salt(("wc_wheel_slot", slot))
                                    .width(148.0)
                                    .selected_text(format!("{}: {}", slot+1, CHOICES[selected].0))
                                    .show_ui(ui, |ui| {
                                        for (index, (label, _)) in CHOICES.iter().enumerate() {
                                            ui.selectable_value(&mut selected, index, *label);
                                        }
                                    });
                                if selected != self.slots[slot] {
                                    self.slots[slot] = selected;
                                    changed = true;
                                }
                            }
                        });
                    }
                    ui.separator();
                    if ui.button("Reset to default").clicked() {
                        self.reset();
                        changed = true;
                    }
                });
            self.settings_open = open;
        }
        changed
    }
}
