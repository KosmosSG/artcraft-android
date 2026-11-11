//! Experimental, opt-in VectorCraft Magic-Pencil 4s wheel. TEST ONLY.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use std::time::{Duration, Instant};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const WAIT: Duration = Duration::from_millis(400);
const LABELS: [&str; 8] = ["Select", "Nodes", "Pen", "Type", "Shapes", "Hand", "Undo", "Redo"];
const ICONS: [&str; 8] = ["dc-selection", "dc-direct", "pen-tool", "dc-type", "shapes", "hand", "undo-2", "redo-2"];
const COMMANDS: [&str; 9] = ["selection", "directSelection", "pen", "type", "rectangle", "hand", "edit.undo", "edit.redo", "eraser"];

pub(crate) struct Wheel {
    pub enabled: bool,
    open: bool,
    swallow_contact: bool,
    center: Option<Pos2>,
    hover: Option<Pos2>,
    single_wait: Option<(Instant, Option<Pos2>)>,
    action: Option<usize>,
    opened_at: Instant,
    last_button: [Option<Instant>; 2],
    message: &'static str,
    message_at: Instant,
}
impl Wheel {
    pub fn new(enabled: bool) -> Self {
        Self { enabled, open: false, swallow_contact: false, center: None, hover: None,
            single_wait: None, action: None, opened_at: Instant::now(),
            last_button: [None, None],
            message: "Hover + single-press: open wheel",
            message_at: Instant::now() }
    }
    /// Exact raster of the approved Vc SVG. Build workflow generates
    /// the transparent RGBA file; no new runtime image decoder is needed.
    fn vc_logo(ctx: &Context) -> egui::TextureHandle {
        let texture_id = Id::new("vc-wheel-user-svg-logo");
        if let Some(existing) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(texture_id)) {
            return existing;
        }
        const PIXELS: &[u8] = include_bytes!("stylus_wheel_vc.rgba");
        const WIDTH: usize = 192;
        const HEIGHT: usize = 120;
        let image = egui::ColorImage::from_rgba_unmultiplied([WIDTH, HEIGHT], PIXELS);
        let texture = ctx.load_texture(
            "vectorcraft-wheel-approved-svg-vc",
            image,
            egui::TextureOptions::LINEAR,
        );
        ctx.data_mut(|d| d.insert_temp(texture_id, texture.clone()));
        texture
    }

    fn notify(&mut self, message: &'static str) {
        self.message = message;
        self.message_at = Instant::now();
    }
    fn mix(a: Color32, b: Color32, fraction: f32) -> Color32 {
        let t = fraction.clamp(0.0, 1.0);
        let channel = |x: u8, y: u8| ((x as f32 * (1.0 - t) + y as f32 * t).round()) as u8;
        Color32::from_rgb(channel(a.r(), b.r()), channel(a.g(), b.g()), channel(a.b(), b.b()))
    }
    pub fn toggle(&mut self, enabled: bool, ctx: &Context) {
        self.enabled = enabled;
        self.open = false;
        self.single_wait = None;
        self.action = None;
        self.last_button = [None, None];
        self.notify(if enabled { "Wheel ON • hover + single press" } else { "Wheel OFF" });
        ctx.data_mut(|d| d.insert_temp(Id::new("vc_stylus_wheel_enabled"), enabled));
        ctx.request_repaint();
    }
    pub fn signal(&mut self, message: &str, ctx: &Context) {
        if !self.enabled { return; }
        let index = match message { "S" => 0, "D" => 1, _ => return };
        let now = Instant::now();
        if self.last_button[index].is_some_and(|when|
            now.duration_since(when) < Duration::from_millis(650)
        ) { return; }
        self.last_button[index] = Some(now);
        match message {
            "S" if self.open => {
                self.open = false;
                self.single_wait = None;
                self.notify("Wheel cancelled");
            }
            "S" => {
                self.single_wait = Some((Instant::now(), self.hover));
                ctx.request_repaint_after(WAIT);
            }
            "D" => {
                self.single_wait = None;
                self.open = false;
                self.action = Some(8);
                self.notify("Double press • Eraser");
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
        Some((((vector.y.atan2(vector.x).to_degrees() + 90.0).rem_euclid(360.0) / 45.0).floor() as usize).min(7))
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        if !self.enabled || blocked {
            self.open = false;
            self.single_wait = None;
            self.action = None;
            return;
        }
        // Java and native input can consume pen keys without egui receiving
        // a KeyboardInput redraw. Poll at a low idle cadence only when opt-in.
        ctx.request_repaint_after(Duration::from_millis(100));
        self.hover = ctx.input(|i| i.pointer.hover_pos()).or(self.hover);
        let mut retained = Vec::with_capacity(raw.events.len());
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerButton {pressed: false, ..} if self.swallow_contact => {
                    self.swallow_contact = false;
                }
                egui::Event::Touch {..} if self.open || self.swallow_contact => {}
                egui::Event::PointerMoved(pos) => {
                    self.hover = Some(pos);
                    retained.push(egui::Event::PointerMoved(pos));
                }
                egui::Event::PointerButton {pos, pressed: true, ..} if self.open => {
                    self.swallow_contact = true;
                    self.action = self.center.and_then(|center| Self::hit(center, pos));
                    self.notify(if self.action.is_some() { "Wheel selection accepted" }
                        else { "Wheel cancelled • tapped outside" });
                    self.open = false;
                    ctx.request_repaint();
                }
                egui::Event::PointerButton {..} if self.open => {}
                egui::Event::Key {key: egui::Key::Escape, pressed: true, ..} if self.open => {
                    self.open = false;
                    self.notify("Wheel cancelled");
                }
                other => retained.push(other),
            }
        }
        raw.events = retained;
        let pen_down = ctx.input(|i| i.pointer.any_down())
            || raw.events.iter().any(|e| matches!(e,
                egui::Event::PointerButton {pressed: true, ..}));
        if pen_down {
            self.single_wait = None;
            if !self.swallow_contact { self.action = None; }
        }
        if let Some((when, point)) = self.single_wait {
            if when.elapsed() >= WAIT {
                self.single_wait = None;
                if let Some(pos) = point.or(self.hover) {
                    self.center = Some(Self::clamped(pos, ctx.content_rect()));
                    self.open = true;
                    self.opened_at = Instant::now();
                    self.notify("Hover to highlight • tap tip to select");
                    ctx.request_repaint();
                } else { self.notify("Hover the pen over the canvas first"); }
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
        let screen = ctx.content_rect();
        let theme = vectorcraft_ui_egui::theme::Tokens::get(&ctx);
        // Brief toast: 1.9 seconds visible, then 0.5 seconds fading out.
        let elapsed = self.message_at.elapsed();
        if elapsed < FEEDBACK_HOLD + FEEDBACK_FADE {
            let alpha = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
                1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32() / FEEDBACK_FADE.as_secs_f32()
            };
            let alpha = alpha.clamp(0.0, 1.0);
            if alpha < 1.0 { ctx.request_repaint_after(Duration::from_millis(40)); }
            egui::Area::new(Id::new("vc-wheel-bottom"))
                .order(Order::Foreground)
                .fixed_pos(pos2((screen.center().x - 175.0).max(screen.min.x),
                    screen.max.y - 43.0))
                .interactable(false)
                .show(&ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(350.0, 31.0), Sense::hover());
                    let painter = ui.painter_at(rect);
                    painter.rect_filled(rect, 13.0, Color32::from_rgba_unmultiplied(
                        theme.panel.r(), theme.panel.g(), theme.panel.b(),
                        (244.0 * alpha) as u8));
                    painter.rect_stroke(rect, 13.0,
                        Stroke::new(1.0, theme.input_border.gamma_multiply(alpha)),
                        StrokeKind::Inside);
                    painter.text(rect.center(), egui::Align2::CENTER_CENTER, self.message,
                        FontId::proportional(11.0), theme.text.gamma_multiply(alpha));
                });
        }
        if !self.open { return; }
        let Some(center) = self.center else { return };
        let t = (self.opened_at.elapsed().as_secs_f32() / 0.18).min(1.0);
        if t < 1.0 { ctx.request_repaint(); }
        let scale = 0.86 + 0.14 * t;
        let size = SIZE * scale;
        let highlighted = self.hover.and_then(|p| Self::hit(center, p));
        let dark = theme.dark;
        egui::Area::new(Id::new("vc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(&ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                let painter = ui.painter_at(rect);
                let c = rect.center();
                // Close, feathered shadow from the approved proposal.
                // Twelve thin low-alpha layers avoid the hard concentric
                // grey rings of the original 22-point spread. Keep radius
                // <= 12 points and position just 2 points below the wheel.
                for step in 0..12 {
                    let spread = (12.0 - step as f32 * 0.82) * scale;
                    let softness = 0.008 + step as f32 * 0.0017;
                    painter.circle_filled(
                        c + vec2(0.8, 2.0) * scale,
                        R * scale + spread,
                        Color32::BLACK.gamma_multiply(softness),
                    );
                }
                painter.circle_filled(c, R * scale,
                    Color32::from_rgba_unmultiplied(
                        theme.panel.r(), theme.panel.g(), theme.panel.b(), 245));
                for i in 0..8 {
                    let degrees = -67.5 + i as f32 * 45.0;
                    let first = (degrees - 21.4).to_radians();
                    let last = (degrees + 21.4).to_radians();
                    let mut vertices = vec![c];
                    for step in 0..=16 {
                        let angle = first + (last - first) * step as f32 / 16.0;
                        vertices.push(c + vec2(angle.cos(), angle.sin()) * R * scale);
                    }
                    let active = highlighted == Some(i);
                    let normal = if i % 2 == 0 {
                        Self::mix(theme.panel, theme.input, if dark { 0.18 } else { 0.30 })
                    } else {
                        Self::mix(theme.panel, theme.input, if dark { 0.68 } else { 0.72 })
                    };
                    let fill = if active {
                        Self::mix(normal, Color32::from_rgb(255, 159, 0), if dark { 0.48 } else { 0.22 })
                    } else { normal };
                    painter.add(Shape::convex_polygon(vertices, fill,
                        Stroke::new(if active { 1.8 } else { 0.65 },
                            if active { Color32::from_rgb(255, 159, 0) }
                            else { theme.input_border.gamma_multiply(0.70) })));
                    let a = degrees.to_radians();
                    let icon_pos = c + vec2(a.cos(), a.sin()) * 87.0 * scale;
                    vectorcraft_ui_egui::icons::paint(ui, ICONS[i],
                        egui::Rect::from_center_size(icon_pos - vec2(0.0, 10.0), vec2(24.0, 24.0) * scale),
                        if active { Color32::from_rgb(255,159,0) } else { theme.text });
                    painter.text(icon_pos + vec2(0.0, 13.0),
                        egui::Align2::CENTER_CENTER, LABELS[i],
                        FontId::proportional(11.0), theme.text_dim);
                }
                painter.circle_stroke(c, R * scale,
                    Stroke::new(0.8, theme.input_border.gamma_multiply(0.58)));
                // Full user-selected round hub, no square tile.
                // The exact uploaded SVG paths are shown here as a texture,
                // retaining the approved orange Vc letterforms.
                let hub_burgundy = Color32::from_rgb(45, 0, 0);
                let hub_orange = Color32::from_rgb(255, 159, 0);
                painter.circle_filled(c, (INNER + 2.0) * scale, hub_burgundy);
                painter.circle_stroke(c, (INNER + 2.0) * scale,
                    Stroke::new(1.3, hub_orange));
                let pc = Self::vc_logo(&ctx);
                let mark_rect = egui::Rect::from_center_size(
                    c - vec2(0.0, 8.0) * scale,
                    vec2(40.0, 25.0) * scale,
                );
                painter.image(
                    pc.id(), mark_rect,
                    egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
                    Color32::WHITE,
                );
                painter.text(c + vec2(0.0, 22.0) * scale,
                    egui::Align2::CENTER_CENTER,
                    highlighted.map(|i| LABELS[i]).unwrap_or("Tools"),
                    FontId::proportional(11.0 * scale), Color32::WHITE);
            });
    }
}
