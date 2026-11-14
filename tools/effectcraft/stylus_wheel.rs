//! EffectCraft Android-only, PhotoCraft-style eight-segment stylus wheel.
//! The device key route is opt-in and separately verifies Magic-Pencil identity.
//! No project/canvas receives input while a visible segment is hovered.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, Ui, pos2, vec2};
use std::{f32::consts::{PI, TAU}, path::PathBuf, time::{Duration, Instant}};
use crate::{dock::PanelKind, icons::{self, Icon}};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
const BLUE: Color32 = Color32::from_rgb(6, 0, 132);
const LAVENDER: Color32 = Color32::from_rgb(153, 153, 255);
const DEFAULT_SLOTS: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
const LABELS: [&str; 14] = [
    "Effect", "Filter", "Layers", "Crop", "Hand", "Adjust", "Undo", "Redo",
    "Select", "Pen", "Text", "Zoom", "Brush", "Rotate",
];
const ICONS: [Icon; 14] = [
    Icon::Fx, Icon::Sparkle, Icon::ShapeLayer, Icon::Region, Icon::Hand,
    Icon::Adjustment, Icon::StepBack, Icon::StepFwd, Icon::Selection,
    Icon::Pen, Icon::Type, Icon::Zoom, Icon::Brush, Icon::Rotate,
];

#[derive(Clone, Copy)]
pub(crate) enum WheelAction {
    Panel(PanelKind),
    CropRegion,
    Invoke(&'static str),
}
fn action(index: usize) -> WheelAction {
    match index {
        0 => WheelAction::Panel(PanelKind::EffectControls),
        1 => WheelAction::Panel(PanelKind::EffectsPresets),
        2 => WheelAction::Panel(PanelKind::Timeline),
        3 => WheelAction::CropRegion,
        4 => WheelAction::Invoke("tool.hand"),
        5 => WheelAction::Panel(PanelKind::Properties),
        6 => WheelAction::Invoke("edit.undo"),
        7 => WheelAction::Invoke("edit.redo"),
        8 => WheelAction::Invoke("tool.selection"),
        9 => WheelAction::Invoke("tool.pen"),
        10 => WheelAction::Invoke("tool.type"),
        11 => WheelAction::Invoke("tool.zoom"),
        12 => WheelAction::Invoke("tool.brush"),
        _ => WheelAction::Invoke("tool.rotate"),
    }
}

pub(crate) struct Wheel {
    pub(crate) enabled: bool,
    pub(crate) settings_open: bool,
    open: bool,
    center: Pos2,
    hover: Option<Pos2>,
    pen_hover: Option<Pos2>,
    slots: [usize; 8],
    size_percent: f32,
    opacity_percent: f32,
    storage: Option<PathBuf>,
    pending: Option<WheelAction>,
    last_press: Option<Instant>,
}

impl Default for Wheel {
    fn default() -> Self {
        Self {
            enabled: false, settings_open: false, open: false,
            center: pos2(0.0, 0.0), hover: None, pen_hover: None, slots: DEFAULT_SLOTS,
            size_percent: 75.0, opacity_percent: 85.0,
            storage: None, pending: None, last_press: None,
        }
    }
}

impl Wheel {
    pub(crate) fn set_storage(&mut self, storage: PathBuf) {
        self.storage = Some(storage.clone());
        let Ok(raw) = std::fs::read_to_string(storage) else { return; };
        let tokens: Vec<_> = raw.trim().split('|').collect();
        if tokens.len() != 5 || tokens[0] != "v1" { return; }
        if let Ok(on) = tokens[1].parse::<u8>() {
            self.enabled = on == 1;
        }
        let slots: Vec<_> = tokens[2].split(',').filter_map(|s| s.parse::<usize>().ok()).collect();
        if slots.len() == 8 && slots.iter().all(|i| *i < LABELS.len())
            && slots.iter().enumerate().all(|(n, v)| !slots[..n].contains(v)) {
            self.slots.copy_from_slice(&slots);
        }
        if let Ok(size) = tokens[3].parse::<f32>() {
            if size.is_finite() { self.size_percent = size.clamp(75.0, 125.0); }
        }
        if let Ok(opacity) = tokens[4].parse::<f32>() {
            if opacity.is_finite() { self.opacity_percent = opacity.clamp(60.0, 100.0); }
        }
    }

    fn save(&self) {
        let Some(path) = &self.storage else { return };
        let content = format!("v1|{}|{}|{:.0}|{:.0}", u8::from(self.enabled),
            self.slots.iter().map(usize::to_string).collect::<Vec<_>>().join(","),
            self.size_percent, self.opacity_percent);
        if let Err(error) = std::fs::write(path, content) {
            log::warn!("EffectCraft stylus wheel preferences: {error}");
        }
    }

    pub(crate) fn toggle(&mut self, ctx: &Context) {
        self.enabled = !self.enabled;
        self.open = false;
        self.pending = None;
        self.save();
        ctx.request_repaint();
    }

    pub(crate) fn open_at_hover(&mut self, ctx: &Context) {
        if !self.enabled || self.settings_open { return; }
        let rect = ctx.content_rect();
        let radius = R * self.scale() + 12.0;
        let where_at = self.hover
            .or_else(|| ctx.input(|i| i.pointer.hover_pos()))
            .unwrap_or(rect.center());
        self.center = pos2(
            where_at.x.clamp(rect.left() + radius, (rect.right() - radius).max(rect.left() + radius)),
            where_at.y.clamp(rect.top() + radius, (rect.bottom() - radius).max(rect.top() + radius))
        );
        self.open = true;
        ctx.request_repaint();
    }

    /// Magic-Pencil 4s-only physical button; Java and native queues verify device identity.
    /// Single press opens/closes, second button picks Hand (safe quick navigation).
    pub(crate) fn pen_button(&mut self, code: i32, ctx: &Context) {
        if !self.enabled || self.settings_open { return; }
        let now = Instant::now();
        if self.last_press.is_some_and(|t| now.duration_since(t) < Duration::from_millis(220)) {
            return;
        }
        self.last_press = Some(now);
        if code == 2 {
            self.pending = Some(WheelAction::Invoke("tool.hand"));
            self.open = false;
        } else if self.open {
            self.open = false;
        } else {
            self.open_at_hover(ctx);
        }
        ctx.request_repaint();
    }

    /// Only verified physical pen input updates this cursor; never use the mouse.
    pub(crate) fn set_pen_hover(&mut self, point: Option<Pos2>, ctx: &Context) {
        if self.pen_hover != point {
            self.pen_hover = point;
            if let Some(point) = point { self.hover = Some(point); }
            ctx.request_repaint();
        }
    }

    /// Exact glyph pixels from the approved launcher tile, no font substitution.
    fn ec_mark(ctx: &Context) -> egui::TextureHandle {
        let id = Id::new("ec-stylus-wheel-approved-mark-v1");
        if let Some(existing) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
            return existing;
        }
        const PIXELS: &[u8] = include_bytes!("stylus_wheel_ec.rgba");
        let image = egui::ColorImage::from_rgba_unmultiplied([192, 126], PIXELS);
        let mark = ctx.load_texture("effectcraft-wheel-launcher-Ec",
            image, egui::TextureOptions::LINEAR);
        ctx.data_mut(|d| d.insert_temp(id, mark.clone()));
        mark
    }

    /// Uniform, 24-point, crisp white vector symbols. Match PhotoCraft's
    /// toolbar weight and icon semantics rather than using playback arrows,
    /// stars for Filters, or tiny inconsistent hand-drawn marks.
    fn paint_slot_icon(painter: &egui::Painter, center: Pos2,
        choice: usize, scale: f32, color: Color32) {
        let stroke = Stroke::new(2.05 * scale, color);
        let p = |x: f32, y: f32| center + vec2((x - 12.0) * scale, (y - 12.0) * scale);
        let line = |nodes: &[(f32, f32)]| {
            painter.add(Shape::line(nodes.iter().map(|&(x, y)| p(x, y)).collect(), stroke));
        };
        match choice {
            0 => { // Effect: uniform magic wand with three clean sparkle crosses
                line(&[(5.0, 20.0), (17.0, 8.0)]);
                line(&[(13.7, 11.3), (17.7, 15.3)]);
                line(&[(16.0, 2.0), (16.0, 6.0)]);
                line(&[(14.0, 4.0), (18.0, 4.0)]);
                line(&[(4.0, 4.0), (4.0, 8.0)]);
                line(&[(2.0, 6.0), (6.0, 6.0)]);
                line(&[(20.0, 16.0), (20.0, 20.0)]);
                line(&[(18.0, 18.0), (22.0, 18.0)]);
            }
            1 => { // Filter: recognizable classic funnel instead of a star
                line(&[(3.5, 4.5), (20.5, 4.5), (14.0, 12.0),
                    (14.0, 18.0), (10.0, 20.5), (10.0, 12.0),
                    (3.5, 4.5)]);
            }
            2 => { // Layers: three consistent tilted diamond layers
                line(&[(12.0, 3.0), (21.0, 8.0), (12.0, 13.0),
                    (3.0, 8.0), (12.0, 3.0)]);
                line(&[(3.0, 12.0), (12.0, 17.0), (21.0, 12.0)]);
                line(&[(3.0, 16.0), (12.0, 21.0), (21.0, 16.0)]);
            }
            3 => { // Crop: opposing L-shaped crop corners
                line(&[(6.0, 3.0), (6.0, 17.0), (21.0, 17.0)]);
                line(&[(3.0, 7.0), (17.0, 7.0), (17.0, 21.0)]);
            }
            5 => { // Adjust: PhotoCraft/Lucide horizontal sliders
                line(&[(4.0, 6.0), (10.0, 6.0)]);
                line(&[(14.0, 6.0), (20.0, 6.0)]);
                painter.circle_stroke(p(12.0, 6.0), 2.0 * scale, stroke);
                line(&[(4.0, 12.0), (7.0, 12.0)]);
                line(&[(11.0, 12.0), (20.0, 12.0)]);
                painter.circle_stroke(p(9.0, 12.0), 2.0 * scale, stroke);
                line(&[(4.0, 18.0), (15.0, 18.0)]);
                line(&[(19.0, 18.0), (20.0, 18.0)]);
                painter.circle_stroke(p(17.0, 18.0), 2.0 * scale, stroke);
            }
            6 | 7 => { // Lucide-style Undo2 / Redo2, 180-degree U-turn
                let flipped = choice == 7;
                let mirror = |x: f32| if flipped { 24.0 - x } else { x };
                line(&[(mirror(9.0), 14.0), (mirror(4.0), 9.0),
                    (mirror(9.0), 4.0)]);
                let mut curve = vec![p(mirror(4.0), 9.0),
                    p(mirror(14.5), 9.0)];
                for i in 1..=24 {
                    let angle = -std::f32::consts::FRAC_PI_2
                        + std::f32::consts::PI * i as f32 / 24.0;
                    curve.push(p(mirror(14.5 + 5.5 * angle.cos()),
                        14.5 + 5.5 * angle.sin()));
                }
                curve.push(p(mirror(11.0), 20.0));
                painter.add(Shape::line(curve, stroke));
            }
            _ => { // Hand, Select, Pen, Zoom use the official editor icon registry
                icons::paint(painter,
                    egui::Rect::from_center_size(center, vec2(24.0, 24.0) * scale),
                    ICONS[choice], color);
            }
        }
    }

    pub(crate) fn take_action(&mut self) -> Option<WheelAction> { self.pending.take() }
    fn scale(&self) -> f32 { self.size_percent / 100.0 }
    fn selected(&self, at: Pos2) -> Option<usize> {
        let delta = at - self.center;
        let radius = delta.length();
        if !(INNER * self.scale()..=R * self.scale()).contains(&radius) { return None; }
        let angle = (delta.y.atan2(delta.x) + PI / 2.0 + PI / 8.0).rem_euclid(TAU);
        Some(((angle / (PI / 4.0)).floor() as usize) % 8)
    }

    /// Modal pointer isolation: while the wheel is open, ALL hover, pen,
    /// touch, drag and scroll events stay off the underlying editor. A press
    /// inside the wheel followed by a release outside cannot select a layer.
    pub(crate) fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        if !self.enabled || blocked || self.settings_open {
            self.open = false;
            return;
        }
        if !self.open {
            for event in &raw.events {
                if let egui::Event::PointerMoved(at) = event { self.hover = Some(*at); }
            }
            return;
        }
        let mut close = false;
        let mut keep = Vec::with_capacity(raw.events.len());
        for event in std::mem::take(&mut raw.events) {
            match event {
                egui::Event::PointerMoved(pos) => self.hover = Some(pos),
                egui::Event::PointerButton { pos, pressed, .. } => {
                    self.hover = Some(pos);
                    if !pressed {
                        if let Some(slot) = self.selected(pos) {
                            self.pending = Some(action(self.slots[slot]));
                        }
                        close = true;
                    } else if self.center.distance(pos) > R * self.scale() {
                        close = true;
                    }
                }
                egui::Event::Touch { pos, phase, .. } => {
                    self.hover = Some(pos);
                    if phase == egui::TouchPhase::End {
                        if let Some(slot) = self.selected(pos) {
                            self.pending = Some(action(self.slots[slot]));
                        }
                        close = true;
                    }
                }
                egui::Event::Key { key: egui::Key::Escape, pressed: true, .. } => close = true,
                egui::Event::PointerGone | egui::Event::Zoom(_) |
                egui::Event::MouseWheel { .. } => {},
                other => keep.push(other),
            }
        }
        if close { self.open = false; }
        keep.push(egui::Event::PointerGone);
        raw.events = keep;
        ctx.request_repaint();
    }

    pub(crate) fn render(&mut self, ctx: &Context) {
        self.customize(ctx);
        if self.open && self.enabled && !self.settings_open {
            let edge = SIZE * self.scale();
            let left_top = self.center - vec2(edge * 0.5, edge * 0.5);
            egui::Area::new(Id::new("effectcraft-stylus-wheel"))
                .order(Order::Foreground).fixed_pos(left_top).interactable(false)
                .show(ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(edge, edge), Sense::hover());
                    self.paint(ui, rect.center(), self.scale(), self.hover.and_then(|p| self.selected(p)));
                });
        }
        if let Some(pos) = self.pen_hover {
            // A pointer is visible immediately on proximity hover, even with
            // the customization dialog open and before any screen contact.
            // It is a non-interactive paint layer, not a synthesized click.
            let painter = ctx.layer_painter(egui::LayerId::new(
                Order::Tooltip, Id::new("ec-stylus-hover-dot")));
            painter.circle_filled(pos, 7.5, BLUE.gamma_multiply(0.20));
            painter.circle_stroke(pos, 6.0, Stroke::new(1.5, LAVENDER));
            painter.circle_filled(pos, 1.7, LAVENDER);
        }
    }

    fn customize(&mut self, ctx: &Context) {
        if !self.settings_open { return; }
        self.open = false;
        let mut showing = true;
        let mut changed = false;
        let window = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("effectcraft-stylus-customize"))
            .open(&mut showing).collapsible(false).resizable(false)
            .default_width(322.0)
            .show(ctx, |ui| {
                ui.label("PhotoCraft-style Default · 8 customizable segments");
                ui.label("The preview is at actual wheel size.");
                ui.separator();
                for slot in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", slot + 1));
                        let mut chosen = self.slots[slot];
                        egui::ComboBox::from_id_salt(("ec-wheel-slot", slot))
                            .width(170.0)
                            .selected_text(LABELS[chosen])
                            .show_ui(ui, |ui| {
                                for (index, label) in LABELS.iter().enumerate() {
                                    ui.selectable_value(&mut chosen, index, *label);
                                }
                            });
                        if chosen != self.slots[slot] {
                            if let Some(previous) = self.slots.iter().position(|n| *n == chosen) {
                                self.slots[previous] = self.slots[slot];
                            }
                            self.slots[slot] = chosen;
                            changed = true;
                        }
                    });
                }
                ui.separator();
                changed |= ui.add(egui::Slider::new(&mut self.size_percent, 75.0..=125.0)
                    .text("Wheel size").suffix("%")).changed();
                changed |= ui.add(egui::Slider::new(&mut self.opacity_percent, 60.0..=100.0)
                    .text("Opacity").suffix("%")).changed();
                if ui.button("Restore Default").clicked() {
                    self.slots = DEFAULT_SLOTS;
                    self.size_percent = 75.0;
                    self.opacity_percent = 85.0;
                    changed = true;
                }
                ui.label("Magic-Pencil 4s: press to open • press again to close");
            });
        self.settings_open = showing;
        if changed { self.save(); ctx.request_repaint(); }
        if let Some(window) = window {
            // Visual-only, physically accurate preview next to the actual dialog.
            // No interactive area is left above the editor after closing settings.
            let dialog = window.response.rect;
            let screen = ctx.content_rect();
            let size = SIZE * self.scale();
            let gap = 18.0;
            let cx = if screen.right() - dialog.right() >= size + gap * 2.0 {
                (dialog.right() + screen.right()) * 0.5
            } else if dialog.left() - screen.left() >= size + gap * 2.0 {
                (screen.left() + dialog.left()) * 0.5
            } else { screen.center().x };
            let center = pos2(cx.clamp(screen.left() + size * 0.5,
                (screen.right() - size * 0.5).max(screen.left() + size * 0.5)),
                dialog.center().y.clamp(screen.top() + size * 0.5,
                (screen.bottom() - size * 0.5).max(screen.top() + size * 0.5)));
            egui::Area::new(Id::new("ec-wheel-actual-size-preview"))
                .order(Order::Foreground)
                .fixed_pos(center - vec2(size * 0.5, size * 0.5))
                .interactable(false)
                .show(ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                    self.paint(ui, rect.center(), self.scale(), None);
                });
        }
    }

    fn paint(&self, ui: &Ui, center: Pos2, scale: f32, selected: Option<usize>) {
        let painter = ui.painter();
        // Broad translucent rings yield the PhotoCraft soft shadow, not a hard halo.
        for layer in (1..=9).rev() {
            let shadow = Color32::from_black_alpha((12 - layer).max(1) as u8);
            painter.circle_filled(center + vec2(0.0, 3.0 * scale),
                (R + layer as f32 * 1.8) * scale, shadow);
        }
        for slot in 0..8 {
            let a = -PI / 2.0 + slot as f32 * PI / 4.0;
            let start = a - PI / 8.0;
            let end = a + PI / 8.0;
            let mut points = vec![center];
            for segment in 0..=18 {
                let t = start + (end - start) * segment as f32 / 18.0;
                points.push(center + vec2(t.cos(), t.sin()) * R * scale);
            }
            let active = selected == Some(slot);
            let (shade, stroke) = if active {
                (Color32::from_rgba_unmultiplied(46, 58, 210,
                        (255.0 * self.opacity_percent / 100.0) as u8),
                 Stroke::new(1.6, LAVENDER))
            } else {
                (Color32::from_rgba_unmultiplied(if slot % 2 == 0 { 72 } else { 66 },
                    if slot % 2 == 0 { 72 } else { 66 },
                    if slot % 2 == 0 { 78 } else { 73 },
                    (255.0 * self.opacity_percent / 100.0) as u8),
                 Stroke::new(0.6, Color32::from_gray(102)))
            };
            painter.add(Shape::convex_polygon(points, shade, stroke));
            let at = center + vec2(a.cos(), a.sin()) * 88.0 * scale;
            let color = Color32::from_rgb(232, 232, 243);
            Self::paint_slot_icon(painter, at - vec2(0.0, 12.0 * scale),
                self.slots[slot], scale, color);
            painter.text(at + vec2(0.0, 14.0 * scale),
                egui::Align2::CENTER_CENTER, LABELS[self.slots[slot]],
                FontId::proportional(11.0 * scale), color);
        }
        painter.circle_stroke(center, R * scale, Stroke::new(0.8, Color32::from_gray(112)));
        painter.circle_filled(center, INNER * scale, BLUE);
        painter.circle_stroke(center, INNER * scale, Stroke::new(1.3, LAVENDER));
        let mark = Self::ec_mark(ui.ctx());
        painter.image(mark.id(),
            egui::Rect::from_center_size(center - vec2(0.0, 8.0) * scale,
                vec2(42.5, 28.05) * scale),
            egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
            Color32::WHITE);
        painter.text(center + vec2(0.0, 24.0 * scale),
            egui::Align2::CENTER_CENTER,
            selected.map(|slot| LABELS[self.slots[slot]]).unwrap_or("EffectCraft"),
            FontId::proportional(9.0 * scale), Color32::WHITE);
    }
}
