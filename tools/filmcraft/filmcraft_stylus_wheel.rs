//! FilmCraft-only PhotoCraft-style stylus wheel for Android, egui 0.37.
//! Never execute synthetic keyboard events: use FilmCraft's command registry.
use egui::{Color32, FontId, Pos2, Sense, Stroke, Vec2, pos2, vec2};
use std::f32::consts::{PI, TAU};
use std::path::PathBuf;

const COMMANDS: [(&str, &str); 8] = [
    ("Razor", "tool.razor"),
    ("Select", "tool.selection"),
    ("Hand", "tool.hand"),
    ("Undo", "edit.undo"),
    ("Redo", "edit.redo"),
    ("Play/Pause", "playback.toggle"),
    ("Zoom +", "view.zoomIn"),
    ("Zoom -", "view.zoomOut"),
];
const DEFAULT_SLOTS: [usize; 8] = [3, 0, 1, 2, 6, 5, 7, 4];
const NAVY: Color32 = Color32::from_rgb(0x00, 0x07, 0x6d);
const LAVENDER: Color32 = Color32::from_rgb(0x9e, 0xa0, 0xe0);
const ACCENT: Color32 = Color32::from_rgb(0x39, 0x50, 0xf2);

pub struct Wheel {
    path: Option<PathBuf>,
    pub enabled: bool,
    pub size: f32,
    pub opacity: f32,
    slots: [usize; 8],
    last_slot: usize,
    settings_open: bool,
}
impl Wheel {
    pub fn new(dir: Option<PathBuf>) -> Self {
        let path = dir.map(|dir| dir.join("filmcraft-stylus-wheel.json"));
        let mut out = Self {
            path, enabled: true, size: 1.0, opacity: 0.91,
            slots: DEFAULT_SLOTS, last_slot: 1, settings_open: false,
        };
        if let Some(path) = &out.path {
            if let Ok(raw) = std::fs::read_to_string(path) {
                if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
                    if let Some(b) = v["enabled"].as_bool() { out.enabled = b; }
                    if let Some(f) = v["size"].as_f64() { out.size = (f as f32).clamp(0.65, 1.55); }
                    if let Some(f) = v["opacity"].as_f64() { out.opacity = (f as f32).clamp(0.25, 1.0); }
                    if let Some(a) = v["slots"].as_array() {
                        if a.len() == 8 {
                            for (i, n) in a.iter().enumerate() {
                                if let Some(n) = n.as_u64().filter(|n| *n < COMMANDS.len() as u64) {
                                    out.slots[i] = n as usize;
                                }
                            }
                        }
                    }
                }
            }
        }
        out
    }

    fn save(&self) {
        if let Some(path) = &self.path {
            if let Some(parent) = path.parent() { let _ = std::fs::create_dir_all(parent); }
            let cfg = serde_json::json!({
                "schema": 1, "enabled": self.enabled, "size": self.size,
                "opacity": self.opacity, "slots": self.slots
            });
            if let Ok(bytes) = serde_json::to_vec_pretty(&cfg) {
                let tmp = path.with_extension("json.tmp");
                if std::fs::write(&tmp, bytes).is_ok() {
                    let _ = std::fs::rename(tmp, path);
                }
            }
        }
    }

    fn radial_index(center: Pos2, pointer: Pos2, radius: f32) -> Option<usize> {
        let v = pointer - center;
        let len = v.length();
        if len < radius * 0.36 || len > radius { return None; }
        let theta = (v.y.atan2(v.x) + PI / 2.0).rem_euclid(TAU);
        Some(((theta / (TAU / 8.0)).floor() as usize).min(7))
    }

    fn draw(&self, ui: &egui::Ui, center: Pos2, radius: f32, hover: Option<usize>) {
        let p = ui.painter();
        let opacity = self.opacity;
        // Gentle diffuse halo, not the hard glowing shadow from older proposals.
        p.circle_filled(center + vec2(0.0, 3.0), radius + 5.0,
            Color32::from_black_alpha(18).gamma_multiply(opacity));
        let width = TAU / 8.0;
        for index in 0..8 {
            let mut pts = Vec::with_capacity(20);
            let first = -PI / 2.0 + index as f32 * width;
            for j in 0..=8 {
                let t = first + width * (j as f32 / 8.0);
                pts.push(center + vec2(t.cos(), t.sin()) * radius);
            }
            for j in (0..=8).rev() {
                let t = first + width * (j as f32 / 8.0);
                pts.push(center + vec2(t.cos(), t.sin()) * (radius * 0.36));
            }
            let chosen = hover == Some(index);
            let fill = if chosen { ACCENT } else { Color32::from_rgb(70, 70, 74) }
                .gamma_multiply(opacity);
            p.add(egui::Shape::convex_polygon(pts, fill,
                Stroke::new(0.75, Color32::from_gray(111).gamma_multiply(opacity))));
            let middle = first + width / 2.0;
            let text_at = center + vec2(middle.cos(), middle.sin()) * (radius * 0.69);
            let label = COMMANDS[self.slots[index]].0;
            p.text(text_at, egui::Align2::CENTER_CENTER, label,
                FontId::proportional((radius / 10.4).clamp(10.0, 16.0)),
                Color32::WHITE.gamma_multiply(opacity));
        }
        p.circle_filled(center, radius * 0.36, NAVY.gamma_multiply(opacity));
        p.circle_stroke(center, radius * 0.36,
            Stroke::new(1.6, LAVENDER.gamma_multiply(opacity)));
        p.text(center + vec2(0.0, -radius * 0.065),
            egui::Align2::CENTER_CENTER, "Fc",
            FontId::proportional(radius * 0.24), LAVENDER.gamma_multiply(opacity));
        p.text(center + vec2(0.0, radius * 0.18), egui::Align2::CENTER_CENTER,
            COMMANDS[self.slots[self.last_slot]].0,
            FontId::proportional((radius * 0.09).max(10.0)), Color32::WHITE.gamma_multiply(opacity));
    }

    fn settings(&mut self, ctx: &egui::Context) {
        if !self.settings_open { return; }
        let mut open = self.settings_open;
        let mut changed = false;
        egui::Window::new("FilmCraft Stylus Wheel")
            .id(egui::Id::new("filmcraft.stylus.settings"))
            .open(&mut open).collapsible(false).resizable(true)
            .default_width(360.0)
            .default_pos(pos2((ctx.available_rect().right() - 420.0).max(20.0), 90.0))
            .show(ctx, |ui| {
                changed |= ui.checkbox(&mut self.enabled, "Enable stylus wheel").changed();
                changed |= ui.add(egui::Slider::new(&mut self.size, 0.65..=1.55)
                    .text("Wheel size").custom_formatter(|n, _| format!("{:.0}%", n * 100.0))).changed();
                changed |= ui.add(egui::Slider::new(&mut self.opacity, 0.25..=1.0)
                    .text("Wheel opacity").custom_formatter(|n, _| format!("{:.0}%", n * 100.0))).changed();
                ui.separator();
                ui.strong("Live preview");
                ui.label("The actual wheel updates at full size while you adjust these controls.");
                let preview_size = (260.0 * self.size).min(276.0);
                let (rect, _) = ui.allocate_exact_size(vec2(preview_size, preview_size), Sense::hover());
                self.draw(ui, rect.center(), preview_size / 2.0 - 5.0, Some(self.last_slot));
                ui.separator();
                ui.strong("Customize the eight shortcut positions");
                for slot in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Position {}", slot + 1));
                        egui::ComboBox::from_id_salt(("fc_wheel_slot", slot))
                            .selected_text(COMMANDS[self.slots[slot]].0)
                            .show_ui(ui, |ui| {
                                for (idx, (label, _)) in COMMANDS.iter().enumerate() {
                                    changed |= ui.selectable_value(&mut self.slots[slot], idx, *label).changed();
                                }
                            });
                    });
                }
                if ui.button("Reset to PhotoCraft-style default").clicked() {
                    self.enabled = true;
                    self.size = 1.0; self.opacity = 0.91;
                    self.slots = DEFAULT_SLOTS;
                    changed = true;
                }
            });
        self.settings_open = open;
        if changed { self.save(); ctx.request_repaint(); }
    }

    pub fn show(&mut self, ctx: &egui::Context) -> Option<&'static str> {
        if ctx.data_mut(|d| d.remove_temp::<bool>(
            egui::Id::new("filmcraft.stylus.settings.open"))).unwrap_or(false) {
            self.settings_open = true;
        }
        self.settings(ctx);
        if !self.enabled { return None; }
        let screen = ctx.available_rect();
        let radius = 117.0 * self.size;
        let diameter = radius * 2.0;
        let where_at = pos2(
            (screen.right() - diameter - 90.0).max(screen.left() + 8.0),
            (screen.bottom() - diameter - 74.0).max(screen.top() + 45.0),
        );
        let result = egui::Area::new(egui::Id::new("filmcraft.stylus.wheel"))
            .order(egui::Order::Foreground)
            .fixed_pos(where_at)
            .interactable(true)
            .show(ctx, |ui| {
                let (rect, response) = ui.allocate_exact_size(
                    vec2(diameter, diameter), Sense::click());
                let hovered = response.hover_pos().and_then(
                    |pos| Self::radial_index(rect.center(), pos, radius));
                self.draw(ui, rect.center(), radius, hovered);
                if response.clicked() {
                    if let Some(i) = response.interact_pointer_pos()
                        .and_then(|pos| Self::radial_index(rect.center(), pos, radius)) {
                        self.last_slot = i;
                        return Some(COMMANDS[self.slots[i]].1);
                    }
                    // Hub is a direct settings shortcut, no hidden inert button.
                    self.settings_open = true;
                }
                None
            }).inner;
        // Foreground Area hit-testing captures clicks/hover before the editor
        // below; use real buttons rather than fake keyboard injections.
        let pad = egui::Area::new(egui::Id::new("filmcraft.stylus.shortcut_pad"))
            .order(egui::Order::Foreground)
            .anchor(egui::Align2::RIGHT_CENTER, vec2(-10.0, 0.0))
            .interactable(true)
            .show(ctx, |ui| {
                egui::Frame::new().fill(Color32::from_gray(60).gamma_multiply(self.opacity))
                    .corner_radius(8.0).inner_margin(egui::Margin::same(5)).show(ui, |ui| {
                    ui.vertical(|ui| {
                        for (label, command) in [
                            ("Undo", "edit.undo"), ("Redo", "edit.redo"),
                            ("Zoom +", "view.zoomIn"), ("Hand", "tool.hand"),
                        ] {
                            if ui.button(label).clicked() { return Some(command); }
                        }
                        if ui.button("Settings").clicked() { self.settings_open = true; }
                        None
                    }).inner
                }).inner
            }).inner;
        result.or(pad)
    }
}
