//! Experimental, opt-in PDFCraft Magic-Pencil 4s wheel. TEST ONLY.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use std::time::{Duration, Instant};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
// Approved PDFCraft launcher background red, used consistently for wheel accents.
const PC_MARK_SCALE: f32 = 1.05; // make just the Pc lettermark 5% larger
// Default wheel diameter on first use and when Reset defaults is selected.
// Previously saved v2 preferences always take precedence.
const DEFAULT_WHEEL_SIZE_PERCENT: f32 = 75.0;
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const WAIT: Duration = Duration::from_millis(400);
// All actions below map to existing PDFCraft tools or commands.
const LABELS: [&str; 12] = ["Select", "Hand", "Ink", "Highlight", "Text", "Eraser", "Undo", "Redo", "Eraser", "Note", "Rectangle", "Zoom"];
const ICONS: [&str; 12] = ["mouse-pointer", "hand", "pencil", "highlighter", "type", "eraser", "undo-2", "redo-2", "eraser", "message-square-plus", "square", "zoom-in"];
const COMMANDS: [&str; 12] = ["view.select_tool", "view.hand_tool", "comment.ink", "comment.highlight", "edit.text", "comment.eraser", "edit.undo", "edit.redo", "comment.eraser", "comment.note", "comment.square", "view.marquee_zoom"];
const DEFAULT_LAYOUT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
const POSITIONS: [&str; 8] = ["Upper right", "Right", "Lower right", "Bottom", "Lower left", "Left", "Upper left", "Top"];

pub(crate) struct Wheel {
    pub enabled: bool,
    open: bool,
    customize_open: bool,
    layout: [usize; 8],
    layout_dirty: bool,
    size_percent: f32,
    opacity_percent: f32,
    pen_hover: Option<Pos2>,
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
        Self { enabled, open: false, customize_open: false, layout: DEFAULT_LAYOUT, layout_dirty: false, size_percent: DEFAULT_WHEEL_SIZE_PERCENT, opacity_percent: 100.0, pen_hover: None, swallow_contact: false, center: None, hover: None,
            single_wait: None, action: None, opened_at: Instant::now(),
            last_button: [None, None],
            message: "Hover + single-press: open wheel",
            message_at: Instant::now() }
    }
    /// Exact raster of the approved Pc launcher artwork. Build workflow generates
    /// the transparent RGBA file; no new runtime image decoder is needed.
    fn pdf_logo(ctx: &Context) -> egui::TextureHandle {
        let texture_id = Id::new("pdf-wheel-user-svg-logo");
        if let Some(existing) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(texture_id)) {
            return existing;
        }
        const PIXELS: &[u8] = include_bytes!("stylus_wheel_pc.rgba");
        const WIDTH: usize = 192;
        const HEIGHT: usize = 120;
        let image = egui::ColorImage::from_rgba_unmultiplied([WIDTH, HEIGHT], PIXELS);
        let texture = ctx.load_texture(
            "pdfcraft-wheel-launcher-mark",
            image,
            egui::TextureOptions::LINEAR,
        );
        ctx.data_mut(|d| d.insert_temp(texture_id, texture.clone()));
        texture
    }

    fn launcher_red() -> Color32 { Color32::from_rgb(251, 14, 0) }

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
        ctx.data_mut(|d| d.insert_temp(Id::new("pdf_stylus_wheel_enabled"), enabled));
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

    /// Read a bounded list of tool indices; malformed or outdated preferences
    /// leave the default layout intact. Never deserialize unchecked action strings.
    pub fn is_visible(&self) -> bool { self.open || self.customize_open }
    pub fn set_pen_hover(&mut self, position: Option<Pos2>) { self.pen_hover = position; self.hover = position; }
    fn display_scale(&self, rect: egui::Rect) -> f32 {
        (self.size_percent / 100.0).min(((rect.width().min(rect.height()) - 20.0) / SIZE).max(0.2))
    }
    pub fn set_layout_string(&mut self, encoded: &str) {
        let fields: Vec<&str> = encoded.split(';').collect();
        let encoded = if fields.len() == 4 && fields[0] == "v2" {
            if let (Ok(size), Ok(opacity)) = (fields[2].parse::<f32>(), fields[3].parse::<f32>()) {
                if size.is_finite() && opacity.is_finite() {
                    self.size_percent = size.clamp(75.0, 150.0);
                    self.opacity_percent = opacity.clamp(40.0, 100.0);
                }
            }
            fields[1]
        } else { encoded };
        let indices: Option<Vec<usize>> = encoded
            .split(',')
            .map(|part| part.trim().parse::<usize>().ok())
            .collect();
        if let Some(indices) = indices {
            if indices.len() == 8 && indices.iter().all(|index| *index < COMMANDS.len()) {
                self.layout.copy_from_slice(&indices);
            }
        }
    }

    pub fn take_layout_change(&mut self) -> Option<String> {
        if !self.layout_dirty { return None; }
        self.layout_dirty = false;
        Some(format!("v2;{};{};{}", self.layout.iter().map(|index| index.to_string()).collect::<Vec<_>>().join(","), self.size_percent, self.opacity_percent))
    }

    pub fn open_customizer(&mut self, ctx: &Context) {
        self.open = false;
        self.single_wait = None;
        self.action = None;
        self.customize_open = true;
        ctx.request_repaint();
    }

    fn clamped(position: Pos2, rect: egui::Rect, scale: f32) -> Pos2 {
        let inset = SIZE * scale * 0.5 + 10.0;
        pos2(position.x.clamp(rect.min.x + inset, (rect.max.x - inset).max(rect.min.x + inset)),
             position.y.clamp(rect.min.y + inset, (rect.max.y - inset).max(rect.min.y + inset)))
    }
    fn hit(center: Pos2, pos: Pos2, scale: f32) -> Option<usize> {
        let vector = (pos - center) / scale;
        if vector.length() < INNER || vector.length() > R + 11.0 { return None; }
        Some((((vector.y.atan2(vector.x).to_degrees() + 90.0).rem_euclid(360.0) / 45.0).floor() as usize).min(7))
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        if !self.enabled || blocked || self.customize_open {
            self.open = false;
            self.single_wait = None;
            self.action = None;
            return;
        }
        // Java and native input can consume pen keys without egui receiving
        // a KeyboardInput redraw. Poll at a low idle cadence only when opt-in.
        ctx.request_repaint_after(Duration::from_millis(100));
        self.hover = self.pen_hover;
        let mut retained = Vec::with_capacity(raw.events.len());
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerButton {pressed: false, ..} if self.swallow_contact => {
                    self.swallow_contact = false;
                }
                egui::Event::Touch {..} if self.open || self.swallow_contact => {}
                egui::Event::PointerMoved(pos) => {
                    // During pen hover, winit may also report a stale mouse/trackpad
                    // position. Keep that event for normal egui input handling, but
                    // do not let it replace the authoritative native pen position.
                    if self.pen_hover.is_none() { self.hover = Some(pos); }
                    if !self.open && !self.swallow_contact {
                        retained.push(egui::Event::PointerMoved(pos));
                    }
                }
                egui::Event::PointerButton {pos, pressed: true, ..} if self.open => {
                    self.swallow_contact = true;
                    self.action = self.center.and_then(|center| Self::hit(center, pos, self.display_scale(ctx.content_rect())));
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
        // Clear egui's previously retained document hover as well as suppressing
        // new motion. Wheel highlighting uses self.hover, independently of egui.
        if self.open || self.swallow_contact {
            retained.push(egui::Event::PointerGone);
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
                if let Some(pos) = point.or(self.pen_hover) {
                    self.center = Some(Self::clamped(pos, ctx.content_rect(), self.display_scale(ctx.content_rect())));
                    self.open = true;
                    self.opened_at = Instant::now();
                    self.notify("Hover to highlight • tap tip to select");
                    ctx.request_repaint();
                } else { self.notify("Hover the pen over the canvas first"); }
            } else {
                ctx.request_repaint_after(WAIT.saturating_sub(when.elapsed()));
            }
        }
        // Opening after the single-button delay must also clear this frame's
        // earlier motion, not just subsequent frames.
        if self.open || self.swallow_contact {
            raw.events.retain(|e| !matches!(e, egui::Event::PointerMoved(_) | egui::Event::PointerGone));
            raw.events.push(egui::Event::PointerGone);
        }
    }
    pub fn take_action(&mut self) -> Option<&'static str> {
        self.action.take().map(|i| COMMANDS[if i == 8 { 8 } else { self.layout[i] }])
    }
    pub fn render(&mut self, ui: &mut Ui) {
        if !self.enabled && !self.customize_open { return; }
        let ctx = ui.ctx().clone();

        if self.customize_open {
            let mut open = true;
            let mut done = false;
            egui::Window::new("Customize Stylus Wheel")
                .id(Id::new("pdf-wheel-settings"))
                .open(&mut open)
                .collapsible(false)
                .resizable(false)
                .default_width(450.0)
                .min_width(450.0)
                .show(&ctx, |ui| {
                    ui.set_min_width(430.0);
                    ui.label("Assign an action to each of the eight wheel segments.");
                    ui.add_space(8.0);
                    ui.heading("Wheel slots");
                    ui.add_space(4.0);

                    // Each assignment has a bordered row AND a framed
                    // selector, so the setting reads as a control instead
                    // of bare text on MagicPad's dark theme.
                    egui::Grid::new("pdf-wheel-slot-grid")
                        .num_columns(1)
                        .spacing(vec2(0.0, 5.0))
                        .show(ui, |ui| {
                            for slot in 0..8 {
                                egui::Frame::new()
                                    .fill(ui.visuals().faint_bg_color)
                                    .stroke(Stroke::new(0.8, ui.visuals().widgets.noninteractive.bg_stroke.color))
                                    .corner_radius(egui::CornerRadius::same(7))
                                    .inner_margin(egui::Margin::symmetric(10, 5))
                                    .show(ui, |ui| {
                                        ui.set_min_width(395.0);
                                        ui.horizontal(|ui| {
                                            ui.add_sized([26.0, 25.0],
                                                egui::Label::new(format!("{:02}", slot + 1)));
                                            ui.add_sized([98.0, 25.0],
                                                egui::Label::new(POSITIONS[slot]));
                                            egui::Frame::new()
                                                .fill(ui.visuals().extreme_bg_color)
                                                .stroke(Stroke::new(1.0,
                                                    ui.visuals().widgets.inactive.bg_stroke.color))
                                                .corner_radius(egui::CornerRadius::same(6))
                                                .inner_margin(egui::Margin::symmetric(7, 2))
                                                .show(ui, |ui| {
                                                    egui::ComboBox::from_id_salt(("pdf-wheel-slot", slot))
                                                        .selected_text(LABELS[self.layout[slot]])
                                                        .width(163.0)
                                                        .show_ui(ui, |ui| {
                                                            for index in 0..LABELS.len() {
                                                                if ui.selectable_value(
                                                                    &mut self.layout[slot], index, LABELS[index]
                                                                ).changed() {
                                                                    self.layout_dirty = true;
                                                                }
                                                            }
                                                        });
                                                });
                                        });
                                    });
                                ui.end_row();
                            }
                        });

                    ui.add_space(12.0);
                    ui.separator();
                    ui.add_space(7.0);
                    ui.heading("Appearance");
                    ui.add_space(5.0);
                    // The app theme makes inactive weak fills transparent for
                    // flat buttons. Sliders also use that fill for their rail.
                    // Override only this appearance card so tracks stay visible.
                    egui::Frame::new()
                        .fill(ui.visuals().faint_bg_color)
                        .stroke(Stroke::new(1.0, ui.visuals().widgets.noninteractive.bg_stroke.color))
                        .corner_radius(egui::CornerRadius::same(7))
                        .inner_margin(egui::Margin::same(10))
                        .show(ui, |ui| {
                            let dark = ui.visuals().dark_mode;
                            let rail = if dark { Color32::from_rgb(100, 108, 122) }
                                else { Color32::from_rgb(165, 175, 190) };
                            // Match the approved Pc launcher background, not the app's blue accent.
                            let accent = Self::launcher_red();
                            let visuals = ui.visuals_mut();
                            visuals.widgets.inactive.weak_bg_fill = rail;
                            visuals.widgets.hovered.weak_bg_fill = rail;
                            visuals.widgets.active.weak_bg_fill = rail;
                            visuals.widgets.inactive.bg_fill = accent;
                            visuals.widgets.hovered.bg_fill = accent;
                            visuals.widgets.active.bg_fill = accent;
                            visuals.selection.bg_fill = accent;
                            ui.spacing_mut().slider_width = 215.0;
                            egui::Grid::new("pdf-wheel-appearance-grid")
                                .num_columns(3)
                                .spacing(vec2(14.0, 14.0))
                                .show(ui, |ui| {
                                    ui.label("Wheel size");
                                    if ui.add_sized([215.0, 28.0],
                                        egui::Slider::new(&mut self.size_percent, 75.0..=150.0)
                                            .trailing_fill(true).show_value(false)
                                    ).changed() { self.layout_dirty = true; }
                                    ui.strong(format!("{:.1}%", self.size_percent));
                                    ui.end_row();
                                    ui.label("Opacity");
                                    if ui.add_sized([215.0, 28.0],
                                        egui::Slider::new(&mut self.opacity_percent, 40.0..=100.0)
                                            .trailing_fill(true).show_value(false)
                                    ).changed() { self.layout_dirty = true; }
                                    ui.strong(format!("{:.1}%", self.opacity_percent));
                                    ui.end_row();
                                });
                            ui.add_space(6.0);
                            ui.small("Size: 75–150%   •   Opacity: 40–100%");
                        });

                    ui.add_space(9.0);
                    ui.small("Preview updates live. All changes save automatically.");
                    ui.add_space(7.0);
                    ui.horizontal(|ui| {
                        if ui.button("Reset defaults").clicked() {
                            self.layout = DEFAULT_LAYOUT;
                            self.size_percent = DEFAULT_WHEEL_SIZE_PERCENT;
                            self.opacity_percent = 100.0;
                            self.layout_dirty = true;
                        }
                        if ui.button("Done").clicked() { done = true; }
                    });
                    ui.small("Double press keeps the Eraser shortcut.");
                });
            self.customize_open = open && !done;
        }
        if !self.enabled && !self.customize_open { return; }
        let screen = ctx.content_rect();
        let theme = pdfcraft_ui_egui::theme::Tokens::get(&ctx);
        // Brief toast: 1.9 seconds visible, then 0.5 seconds fading out.
        let elapsed = self.message_at.elapsed();
        if elapsed < FEEDBACK_HOLD + FEEDBACK_FADE {
            let alpha = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
                1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32() / FEEDBACK_FADE.as_secs_f32()
            };
            let alpha = alpha.clamp(0.0, 1.0);
            if alpha < 1.0 { ctx.request_repaint_after(Duration::from_millis(40)); }
            egui::Area::new(Id::new("pdf-wheel-bottom"))
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
                        Stroke::new(1.0, theme.border.gamma_multiply(alpha)),
                        StrokeKind::Inside);
                    painter.text(rect.center(), egui::Align2::CENTER_CENTER, self.message,
                        FontId::proportional(11.0), theme.text.gamma_multiply(alpha));
                });
        }
        if !self.open && !self.customize_open { return; }
        let scale = self.display_scale(screen);
        let center = if self.customize_open { Self::clamped(pos2(screen.right() - SIZE * scale * 0.5 - 28.0, screen.center().y), screen, scale) }
            else if let Some(c) = self.center { Self::clamped(c, screen, scale) } else { return };
        let t = (self.opened_at.elapsed().as_secs_f32() / 0.18).min(1.0);
        if t < 1.0 { ctx.request_repaint(); }
        // Geometry and hit targets always share the same configured scale.
        let size = SIZE * scale;
        let highlighted = self.hover.and_then(|p| Self::hit(center, p, scale));
        let dark = ui.visuals().dark_mode;
        egui::Area::new(Id::new("pdf-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(&ctx, |ui| {
                ui.set_opacity(self.opacity_percent / 100.0);
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
                        Self::mix(theme.panel, theme.field, if dark { 0.18 } else { 0.30 })
                    } else {
                        Self::mix(theme.panel, theme.field, if dark { 0.68 } else { 0.72 })
                    };
                    let fill = if active {
                        Self::mix(normal, Color32::from_rgb(251, 180, 176), if dark { 0.48 } else { 0.22 })
                    } else { normal };
                    painter.add(Shape::convex_polygon(vertices, fill,
                        Stroke::new(if active { 1.8 } else { 0.65 },
                            if active { Color32::from_rgb(251, 180, 176) }
                            else { theme.border.gamma_multiply(0.70) })));
                    let a = degrees.to_radians();
                    let icon_pos = c + vec2(a.cos(), a.sin()) * 87.0 * scale;
                    pdfcraft_ui_egui::icons::paint(ui,
                        egui::Rect::from_center_size(icon_pos - vec2(0.0, 10.0), vec2(24.0, 24.0) * scale), ICONS[self.layout[i]], 24.0 * scale,
                        if active { Color32::from_rgb(251,180,176) } else { theme.text });
                    painter.text(icon_pos + vec2(0.0, 13.0),
                        egui::Align2::CENTER_CENTER, LABELS[self.layout[i]],
                        FontId::proportional(11.0 * scale), theme.text_muted);
                }
                // Branded outer border, matching the Pc launcher and customization sliders.
                // Scale line width with the wheel to keep the ring visually balanced.
                painter.circle_stroke(c, R * scale,
                    Stroke::new(2.0 * scale, Self::launcher_red()));
                // Full user-selected round hub, no square tile.
                // The exact uploaded launcher artwork paths are shown here as a texture,
                // retaining the approved pale-pink Pc letterforms.
                let hub_red = Self::launcher_red();
                let hub_pink = Color32::from_rgb(251, 180, 176);
                painter.circle_filled(c, (INNER + 2.0) * scale, hub_red);
                painter.circle_stroke(c, (INNER + 2.0) * scale,
                    Stroke::new(1.3, hub_pink));
                let pc = Self::pdf_logo(&ctx);
                let mark_rect = egui::Rect::from_center_size(
                    c - vec2(0.0, 8.0) * scale,
                    vec2(36.0, 22.5) * (PC_MARK_SCALE * scale),
                );
                painter.image(
                    pc.id(), mark_rect,
                    egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
                    Color32::WHITE,
                );
                painter.text(c + vec2(0.0, 22.0) * scale,
                    egui::Align2::CENTER_CENTER,
                    highlighted.map(|i| LABELS[self.layout[i]]).unwrap_or("Tools"),
                    FontId::proportional(11.0 * scale), Color32::WHITE);
            });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn wheel_size_75_default_reset_and_preserved_saved_choice() {
        let mut wheel = Wheel::new(true);
        assert_eq!(wheel.size_percent, DEFAULT_WHEEL_SIZE_PERCENT);
        assert_eq!(wheel.opacity_percent, 100.0);
        // Saved preferences continue to override the first-use default.
        wheel.set_layout_string("v2;0,1,2,3,4,5,6,7;123;85");
        assert_eq!((wheel.size_percent, wheel.opacity_percent), (123.0, 85.0));
        // The Reset defaults button assigns DEFAULT_WHEEL_SIZE_PERCENT,
        // keeping the lowest supported slider value within the existing range.
        assert_eq!(DEFAULT_WHEEL_SIZE_PERCENT, 75.0);
    }
    #[test] fn approved_pc_brand_color_and_five_percent_lettermark() {
        assert_eq!(Wheel::launcher_red(), Color32::from_rgb(251, 14, 0));
        assert!((PC_MARK_SCALE - 1.05).abs() < f32::EPSILON);
        // Rendering-only change: saved layout values and hit geometry remain unchanged.
        assert_eq!(R, 128.0);
        assert_eq!(INNER, 46.0);
    }
    #[test] fn saved_preferences_round_trip_and_bounds() {
        let mut wheel=Wheel::new(true);
        wheel.set_layout_string("v2;7,6,5,4,3,2,1,0;120;65");
        assert_eq!(wheel.layout,[7,6,5,4,3,2,1,0]);
        assert_eq!((wheel.size_percent,wheel.opacity_percent),(120.0,65.0));
        wheel.layout_dirty=true;
        let saved=wheel.take_layout_change().unwrap();
        let mut restored=Wheel::new(false);restored.set_layout_string(&saved);
        assert_eq!(restored.layout,wheel.layout);
        assert_eq!((restored.size_percent,restored.opacity_percent),(120.0,65.0));
        restored.set_layout_string("v2;99;900;-20");
        assert_eq!(restored.layout,wheel.layout);
        assert_eq!((restored.size_percent,restored.opacity_percent),(150.0,40.0));
        restored.set_layout_string("v2;bad;NaN;inf");
        assert!(restored.size_percent.is_finite() && restored.opacity_percent.is_finite());
    }
    #[test] fn scaled_hit_targets_and_dead_zone() {
        for scale in [0.75,1.0,1.5] {
            let center=pos2(300.0,300.0);
            assert_eq!(Wheel::hit(center,center,scale),None);
            assert_eq!(Wheel::hit(center,center+vec2(200.0,0.0)*scale,scale),None);
            for slot in 0..8 {
                let angle=(-67.5+slot as f32*45.0).to_radians();
                let p=center+vec2(angle.cos(),angle.sin())*90.0*scale;
                assert_eq!(Wheel::hit(center,p,scale),Some(slot));
            }
        }
    }
    #[test] fn customized_action_and_double_eraser() {
        let ctx=Context::default();let mut wheel=Wheel::new(true);
        wheel.set_layout_string("7,6,5,4,3,2,1,0");wheel.action=Some(0);
        assert_eq!(wheel.take_action(),Some("edit.redo"));
        wheel.signal("D",&ctx);assert_eq!(wheel.take_action(),Some("comment.eraser"));
    }
    #[test] fn wheel_contact_never_reaches_document() {
        let ctx=Context::default();let mut wheel=Wheel::new(true);
        wheel.open=true;wheel.center=Some(pos2(300.0,300.0));
        let mut raw=RawInput::default();
        raw.events.push(egui::Event::PointerButton{pos:pos2(380.0,260.0),button:egui::PointerButton::Primary,pressed:true,modifiers:egui::Modifiers::NONE});
        wheel.capture(&ctx,&mut raw,false);assert!(raw.events.iter().all(|e| matches!(e, egui::Event::PointerGone)));
        raw.events.push(egui::Event::PointerButton{pos:pos2(380.0,260.0),button:egui::PointerButton::Primary,pressed:false,modifiers:egui::Modifiers::NONE});
        wheel.capture(&ctx,&mut raw,false);assert!(raw.events.iter().all(|e| matches!(e, egui::Event::PointerGone)));
    }
    #[test]
    fn open_wheel_clears_document_hover_and_keeps_local_highlight() {
        let ctx = Context::default();
        let mut wheel = Wheel::new(true);
        wheel.open = true;
        wheel.center = Some(pos2(300.0, 300.0));
        let point = pos2(300.0, 220.0);
        let mut raw = RawInput::default();
        raw.events.push(egui::Event::PointerMoved(point));
        wheel.capture(&ctx, &mut raw, false);
        assert_eq!(wheel.hover, Some(point));
        assert!(raw.events.iter().any(|e| matches!(e, egui::Event::PointerGone)));
        assert!(!raw.events.iter().any(|e| matches!(e, egui::Event::PointerMoved(_))));
        assert!(wheel.take_action().is_none());
        wheel.open = false;
        raw.events = vec![egui::Event::PointerMoved(point)];
        wheel.capture(&ctx, &mut raw, false);
        assert!(matches!(raw.events.as_slice(), [egui::Event::PointerMoved(_)]));
    }

}
