//! Experimental, opt-in PhotoCraft Magic-Pencil 4s wheel. TEST ONLY.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use std::time::{Duration, Instant};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 284.0;
const WAIT: Duration = Duration::from_millis(400);
const LABELS: [&str; 6] = ["Undo", "Brush", "Eraser", "Hand", "Picker", "Redo"];
const ICONS: [&str; 6] = ["U", "B", "E", "H", "I", "R"];
const COMMANDS: [&str; 6] = [
    "edit.undo", "tools.select.brush", "tools.select.eraser",
    "tools.select.hand", "tools.select.eyedropper", "edit.redo"
];

pub(crate) struct Wheel {
    pub enabled: bool,
    open: bool,
    center: Option<Pos2>,
    hover: Option<Pos2>,
    single_wait: Option<(Instant, Option<Pos2>)>,
    action: Option<usize>,
    opened_at: Instant,
    message: &'static str,
}
impl Wheel {
    pub fn new(enabled: bool) -> Self {
        Self { enabled, open: false, center: None, hover: None,
            single_wait: None, action: None, opened_at: Instant::now(),
            message: "Hover + single-press: open wheel" }
    }
    pub fn toggle(&mut self, enabled: bool, ctx: &Context) {
        self.enabled = enabled;
        self.open = false;
        self.single_wait = None;
        self.action = None;
        self.message = if enabled { "Wheel ON • hover + single press" } else { "Wheel OFF" };
        ctx.data_mut(|d| d.insert_temp(Id::new("pc_stylus_wheel_enabled"), enabled));
        ctx.request_repaint();
    }
    pub fn signal(&mut self, message: &str, ctx: &Context) {
        if !self.enabled { return; }
        match message {
            "S" if self.open => {
                self.open = false;
                self.single_wait = None;
                self.message = "Wheel cancelled";
            }
            "S" => {
                self.single_wait = Some((Instant::now(), self.hover));
                ctx.request_repaint_after(WAIT);
            }
            "D" => {
                self.single_wait = None;
                self.open = false;
                self.action = Some(2);
                self.message = "Double press • Eraser";
            }
            _ => {}
        }
        ctx.request_repaint();
    }
    fn clamped(position: Pos2, rect: egui::Rect) -> Pos2 {
        let inset = SIZE * 0.5 + 10.0;
        pos2(position.x.clamp(rect.min.x + inset, (rect.max.x - inset).max(rect.min.x + inset)),
             position.y.clamp(rect.min.y + inset, (rect.max.y - inset).max(rect.min.y + inset)))
    }
    fn hit(center: Pos2, pos: Pos2) -> Option<usize> {
        let vector = pos - center;
        if vector.length() < INNER || vector.length() > R + 11.0 { return None; }
        Some((((vector.y.atan2(vector.x).to_degrees() + 120.0).rem_euclid(360.0) / 60.0).floor() as usize).min(5))
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        if !self.enabled || blocked {
            self.open = false;
            self.single_wait = None;
            self.action = None;
            return;
        }
        self.hover = ctx.input(|i| i.pointer.hover_pos()).or(self.hover);
        let mut retained = Vec::with_capacity(raw.events.len());
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerMoved(pos) => {
                    self.hover = Some(pos);
                    retained.push(egui::Event::PointerMoved(pos));
                }
                egui::Event::PointerButton {pos, pressed: true, ..} if self.open => {
                    self.action = self.center.and_then(|center| Self::hit(center, pos));
                    self.message = if self.action.is_some() { "Wheel selection accepted" }
                        else { "Wheel cancelled • tapped outside" };
                    self.open = false;
                    ctx.request_repaint();
                }
                egui::Event::PointerButton {..} if self.open => {}
                egui::Event::Key {key: egui::Key::Escape, pressed: true, ..} if self.open => {
                    self.open = false;
                    self.message = "Wheel cancelled";
                }
                other => retained.push(other),
            }
        }
        raw.events = retained;
        let pen_down = ctx.input(|i| i.pointer.any_down())
            || raw.events.iter().any(|e| matches!(e,
                egui::Event::PointerButton {pressed: true, ..}));
        if pen_down { self.single_wait = None; }
        if let Some((when, point)) = self.single_wait {
            if when.elapsed() >= WAIT {
                self.single_wait = None;
                if let Some(pos) = point.or(self.hover) {
                    self.center = Some(Self::clamped(pos, ctx.screen_rect()));
                    self.open = true;
                    self.opened_at = Instant::now();
                    self.message = "Hover to highlight • tap tip to select";
                    ctx.request_repaint();
                } else { self.message = "Hover the pen over the canvas first"; }
            } else {
                ctx.request_repaint_after(WAIT.saturating_sub(when.elapsed()));
            }
        }
    }
    pub fn take_action(&mut self) -> Option<&'static str> {
        self.action.take().map(|i| COMMANDS[i])
    }
    pub fn render(&self, ui: &mut Ui) {
        if !self.enabled { return; }
        let ctx = ui.ctx().clone();
        let screen = ctx.screen_rect();
        let y = screen.max.y - 43.0;
        egui::Area::new(Id::new("pc-wheel-bottom"))
            .order(Order::Foreground)
            .fixed_pos(pos2((screen.center().x - 175.0).max(screen.min.x), y))
            .interactable(false)
            .show(&ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(350.0, 31.0), Sense::hover());
                let painter = ui.painter_at(rect);
                painter.rect_filled(rect, 13.0, Color32::from_rgba_unmultiplied(19, 30, 45, 233));
                painter.rect_stroke(rect, 13.0, Stroke::new(1.0, Color32::from_rgb(77, 118, 153)), StrokeKind::Inside);
                painter.text(rect.center(), egui::Align2::CENTER_CENTER, self.message,
                    FontId::proportional(11.0), Color32::from_rgb(229, 240, 251));
            });
        if !self.open { return; }
        let Some(center) = self.center else { return };
        let t = (self.opened_at.elapsed().as_secs_f32() / 0.18).min(1.0);
        if t < 1.0 { ctx.request_repaint(); }
        let scale = 0.86 + 0.14 * t;
        let size = SIZE * scale;
        let highlighted = self.hover.and_then(|p| Self::hit(center, p));
        egui::Area::new(Id::new("pc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(&ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                let painter = ui.painter_at(rect);
                let c = rect.center();
                painter.circle_filled(c + vec2(2.0, 6.0), 134.0 * scale,
                    Color32::from_rgba_unmultiplied(2, 8, 20, 122));
                painter.circle_filled(c, R * scale, Color32::from_rgb(24, 35, 52));
                for i in 0..6 {
                    let degrees = -90.0 + i as f32 * 60.0;
                    let first = (degrees - 28.4).to_radians();
                    let last = (degrees + 28.4).to_radians();
                    let mut vertices = vec![c];
                    for step in 0..=16 {
                        let angle = first + (last - first) * step as f32 / 16.0;
                        vertices.push(c + vec2(angle.cos(), angle.sin()) * R * scale);
                    }
                    let active = highlighted == Some(i);
                    let fill = if active { Color32::from_rgb(49, 112, 166) }
                        else if i % 2 == 0 { Color32::from_rgb(36, 52, 73) }
                        else { Color32::from_rgb(30, 44, 64) };
                    painter.add(Shape::convex_polygon(vertices, fill,
                        Stroke::new(if active {2.0} else {0.8},
                            if active { Color32::from_rgb(153, 218, 255) }
                            else { Color32::from_rgb(79, 105, 134) })));
                    let a = degrees.to_radians();
                    let icon_pos = c + vec2(a.cos(), a.sin()) * 87.0 * scale;
                    painter.text(icon_pos - vec2(0.0, 10.0),
                        egui::Align2::CENTER_CENTER, ICONS[i],
                        FontId::proportional(if active {22.0} else {19.0}),
                        Color32::WHITE);
                    painter.text(icon_pos + vec2(0.0, 13.0),
                        egui::Align2::CENTER_CENTER, LABELS[i],
                        FontId::proportional(11.0), Color32::from_rgb(209, 229, 250));
                }
                painter.circle_filled(c, (INNER + 2.0) * scale, Color32::from_rgb(14, 25, 40));
                painter.circle_stroke(c, (INNER + 2.0) * scale,
                    Stroke::new(2.0, Color32::from_rgb(124, 171, 217)));
                painter.text(c - vec2(0.0, 7.0), egui::Align2::CENTER_CENTER, "Pc",
                    FontId::proportional(19.0), Color32::WHITE);
                painter.text(c + vec2(0.0, 14.0), egui::Align2::CENTER_CENTER,
                    highlighted.map(|i| LABELS[i]).unwrap_or("Tools"),
                    FontId::proportional(10.0), Color32::from_rgb(176, 216, 249));
            });
    }
}
