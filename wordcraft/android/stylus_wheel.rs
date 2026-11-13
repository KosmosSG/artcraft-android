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
const CYAN: Color32 = Color32::from_rgb(62, 195, 255);
const HUB: Color32 = Color32::from_rgb(10, 54, 116);

pub struct Wheel {
    pub visible: bool,
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
            visible: true,
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
            if let Some(v) = value["visible"].as_bool() { wheel.visible = v; }
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
        json!({"visible":self.visible, "size":self.size, "opacity":self.opacity,
               "slots":self.slots}).to_string()
    }

    pub fn reset(&mut self) {
        self.size = 284.0;
        self.opacity = 0.82;
        self.slots = DEFAULT;
        self.visible = true;
    }

    pub fn center(&self, screen: Rect) -> Pos2 {
        let radius = self.size * 0.5;
        let x = screen.right() - radius - 92.0;
        let y = screen.bottom() - radius - 92.0;
        egui::pos2(
            x.clamp(screen.left() + radius + 8.0, (screen.right() - radius - 8.0).max(screen.left() + radius + 8.0)),
            y.clamp(screen.top() + radius + 8.0, (screen.bottom() - radius - 8.0).max(screen.top() + radius + 8.0)),
        )
    }

    pub fn owns(&self, pos: Pos2, screen: Rect) -> bool {
        self.visible && pos.distance_sq(self.center(screen)) <= (self.size * 0.5 + 5.0).powi(2)
    }

    fn sector(&self, pos: Pos2, screen: Rect) -> Option<usize> {
        if !self.owns(pos, screen) { return None; }
        let c = self.center(screen);
        if pos.distance(c) <= self.size * 0.235 { return None; }
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

    /// WC_WHEEL_HOVER_ISOLATION_V1: swallow only events belonging to the radial
    /// overlay. Other touch contacts, trackpad pan/pinch and keyboard keys pass.
    /// Ownership persists until lift, even when the contact drags off the ring.
    pub fn filter_input(&mut self, raw: &mut egui::RawInput, screen: Rect) {
        if !self.visible {
            self.owned_mouse = false;
            self.mouse_down = None;
            self.touch_down = None;
            self.hovered = None;
            return;
        }
        let mut events = Vec::with_capacity(raw.events.len() + 1);
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerMoved(pos) if self.owns(pos, screen) || self.owned_mouse => {
                    self.hovered = self.sector(pos, screen);
                    // Clear the previous document hover once before the wheel
                    // receives subsequent movements; the editor must never see it.
                    events.push(egui::Event::PointerGone);
                }
                egui::Event::PointerButton { pos, button: egui::PointerButton::Primary, pressed, .. }
                    if self.owns(pos, screen) || self.owned_mouse =>
                {
                    if pressed {
                        self.owned_mouse = true;
                        self.mouse_down = self.sector(pos, screen);
                        self.hovered = self.mouse_down;
                    } else {
                        let release = self.sector(pos, screen);
                        if let (Some(start), Some(end)) = (self.mouse_down.take(), release) {
                            if start == end { self.queue(start); }
                        }
                        self.owned_mouse = false;
                    }
                    events.push(egui::Event::PointerGone);
                }
                egui::Event::Touch { device_id, id, phase, pos, .. }
                    if self.owns(pos, screen) ||
                       self.touch_down.is_some_and(|(d, t, _)| d == device_id.0 && t == id.0) =>
                {
                    match phase {
                        egui::TouchPhase::Start => {
                            if let Some(slot) = self.sector(pos, screen) {
                                self.touch_down = Some((device_id.0, id.0, slot));
                            }
                        }
                        egui::TouchPhase::End => {
                            if let Some((d, t, start)) = self.touch_down {
                                if d == device_id.0 && t == id.0 {
                                    if self.sector(pos, screen) == Some(start) { self.queue(start); }
                                    self.touch_down = None;
                                }
                            }
                        }
                        egui::TouchPhase::Cancel => { self.touch_down = None; }
                        egui::TouchPhase::Move => {
                            self.hovered = self.sector(pos, screen);
                        }
                    }
                    events.push(egui::Event::PointerGone);
                }
                egui::Event::MouseWheel { .. } if self.hovered.is_some() => {
                    // Never scroll/select the document through the wheel.
                }
                egui::Event::Zoom(_) if self.hovered.is_some() => {}
                e => {
                    if matches!(&e, egui::Event::PointerMoved(_)) { self.hovered = None; }
                    events.push(e);
                }
            }
        }
        raw.events = events;
    }

    /// Render the same wheel function in the live canvas and settings preview.
    /// No screenshot thumbnail scaling: size and opacity are both real values.
    pub fn paint(&self, painter: &egui::Painter, center: Pos2, size: f32, opacity: f32,
                 selected: Option<usize>) {
        let radius = size * 0.5;
        // Layered low-alpha shadows rather than a hard black halo.
        for (extra, alpha) in [(17.0, 3), (12.0, 5), (7.0, 7), (3.0, 10)] {
            painter.circle_filled(center + egui::vec2(2.0, 3.0),
                radius + extra, Color32::from_black_alpha(alpha));
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
                points.push(center + egui::vec2(a.cos(), a.sin()) * radius * 0.235);
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
            let icon = match label {
                "Undo" => "↶", "Redo" => "↷", "Pen" | "Pencil" => "✎",
                "Eraser" => "◇", "Highlight" => "▱", "Select" => "⌖",
                "Copy" => "▣", "Paste" => "▤", "Bold" => "B",
                "Italic" => "I", "Save" => "▣", "Lasso" => "⌁", _ => "•"
            };
            painter.text(icon_pos, egui::Align2::CENTER_CENTER, icon,
                FontId::proportional((size * 0.088).clamp(15.0, 30.0)), Color32::WHITE);
            painter.text(icon_pos + egui::vec2(0.0, size * 0.086),
                egui::Align2::CENTER_CENTER, label,
                FontId::proportional((size * 0.047).clamp(9.0, 16.0)),
                Color32::from_rgb(225, 231, 240));
        }
        painter.circle_filled(center, radius * 0.235, HUB);
        painter.circle_stroke(center, radius * 0.235, Stroke::new(1.8, CYAN));
        painter.text(center + egui::vec2(0.0, -size * 0.032), egui::Align2::CENTER_CENTER,
            "Wc", FontId::proportional(size * 0.15), CYAN);
        painter.text(center + egui::vec2(0.0, size * 0.105), egui::Align2::CENTER_CENTER,
            CHOICES[self.slots[self.active]].0,
            FontId::proportional((size * 0.044).max(9.0)), Color32::WHITE);
        painter.circle_stroke(center, radius, Stroke::new(1.0, Color32::from_gray(124)));
    }

    pub fn show(&mut self, ctx: &egui::Context) -> bool {
        let mut changed = false;
        let screen = ctx.input(|i| i.screen_rect());
        if self.visible {
            let at = self.center(screen) - Vec2::splat(self.size / 2.0);
            egui::Area::new(egui::Id::new("wc_stylus_wheel_area"))
                .order(egui::Order::Foreground)
                .interactable(false)
                .fixed_pos(at)
                .show(ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(Vec2::splat(self.size), egui::Sense::hover());
                    self.paint(ui.painter(), rect.center(), self.size, self.opacity, self.hovered);
                });
        }
        if self.settings_open {
            let mut open = true;
            egui::Window::new("WordCraft Stylus Wheel Customization")
                .id(egui::Id::new("wc_stylus_wheel_settings"))
                .open(&mut open)
                .default_width(450.0)
                .default_pos(egui::pos2(screen.left() + 28.0, screen.top() + 80.0))
                .show(ctx, |ui| {
                    ui.label("PhotoCraft-style wheel • WordCraft blue and cyan");
                    ui.separator();
                    changed |= ui.add(egui::Slider::new(&mut self.size, 170.0..=380.0)
                        .text("Wheel size").suffix(" pt")).changed();
                    let percent = (self.opacity * 100.0).round();
                    changed |= ui.add(egui::Slider::new(&mut self.opacity, 0.25..=1.0)
                        .text("Wheel opacity")).changed();
                    ui.small(format!("Opacity: {percent:.0}% • Full-size, live preview"));
                    ui.separator();
                    ui.label("Live preview (same geometry and opacity as on the canvas)");
                    egui::ScrollArea::horizontal().max_height(402.0).show(ui, |ui| {
                        let (rect, _) = ui.allocate_exact_size(Vec2::splat(self.size + 30.0),
                            egui::Sense::hover());
                        self.paint(ui.painter(), rect.center(), self.size, self.opacity, Some(self.active));
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
