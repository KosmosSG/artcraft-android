//! Experimental, opt-in PhotoCraft Magic-Pencil 4s wheel. TEST ONLY.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use std::time::{Duration, Instant};
use std::path::PathBuf;

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const WAIT: Duration = Duration::from_millis(400);
// First eight entries of the user-facing "Default" preset are chosen via DEFAULT_SLOTS.
// Keep command IDs grounded in official Storytold PhotoCraft v0.22.0.
const LABELS: [&str; 15] = [
    "Undo", "Brush", "Eraser", "Hand", "Picker", "Redo", "Layers",
    "Adjust", "Move", "Crop", "Selection", "Type", "Fill", "Shape", "Transform",
];
// Tool marks are drawn as paths; unsupported font glyphs rendered as tofu
// boxes on MagicOS/egui and must never be used for wheel iconography.
const COMMANDS: [&str; 15] = [
    "edit.undo", "tools.select.brush", "tools.select.eraser",
    "tools.select.hand", "tools.select.eyedropper", "edit.redo",
    "window.toggle.layers", "window.toggle.properties", "tools.select.move",
    "tools.select.crop", "tools.select.rectMarquee", "tools.select.type",
    "tools.select.paintBucket", "tools.select.rectangle", "edit.freeTransform",
];
// The names below come from the same official PhotoCraft icon registry used
// by toolbar::toolbar via icons::tool_icon. No approximated hand-drawn marks.
const TOOLBAR_ICONS: [&str; 15] = [
    "undo-2", "brush", "eraser", "hand", "pipette", "redo-2",
    "layers", "sliders-horizontal", "move", "crop", "square-dashed",
    "type", "paint-bucket", "rectangle-horizontal", "scaling",
];
const DEFAULT_SLOTS: [usize; 8] = [1, 2, 6, 7, 3, 4, 5, 0];
const WHEEL_STYLE: &str = "Default";

pub(crate) struct Wheel {
    pub enabled: bool,
    pub settings_open: bool,
    slots: [usize; 8],
    size_percent: f32,
    opacity_percent: f32,
    settings_path: Option<PathBuf>,
    open: bool,
    center: Option<Pos2>,
    hover: Option<Pos2>,
    // True only while a pointer is within the visible wheel; reset on exit.
    hover_blocked: bool,
    single_wait: Option<(Instant, Option<Pos2>)>,
    action: Option<&'static str>,
    opened_at: Instant,
    last_button: [Option<Instant>; 2],
    message: &'static str,
    message_at: Instant,
}
impl Wheel {
    pub fn new(enabled: bool, files_dir: Option<PathBuf>) -> Self {
        let settings_path = files_dir.map(|p| p.join("photocraft-stylus-wheel-default.v1"));
        let mut slots = DEFAULT_SLOTS;
        let mut size_percent = 100.0f32;
        let mut opacity_percent = 85.0f32;
        // A short, versioned app-private file. Invalid files fall back to Default.
        if let Some(stored) = settings_path.as_ref().and_then(|p| std::fs::read_to_string(p).ok()) {
            let fields: Vec<_> = stored.trim().split('|').collect();
            if fields.len() == 4 && fields[0] == "v1" {
                let chosen: Vec<usize> = fields[1].split(',')
                    .filter_map(|n| n.parse::<usize>().ok()).collect();
                if chosen.len() == 8
                    && chosen.iter().all(|n| *n < LABELS.len())
                    && chosen.iter().enumerate().all(|(i, n)|
                        !chosen[..i].contains(n))
                {
                    slots.copy_from_slice(&chosen);
                }
                if let Ok(value) = fields[2].parse::<f32>() {
                    if value.is_finite() { size_percent = value.clamp(75.0, 125.0); }
                }
                if let Ok(value) = fields[3].parse::<f32>() {
                    if value.is_finite() { opacity_percent = value.clamp(60.0, 100.0); }
                }
            }
        }
        Self { enabled, settings_open: false, slots, size_percent, opacity_percent,
            settings_path, open: false, center: None, hover: None, hover_blocked: false,
            single_wait: None, action: None, opened_at: Instant::now(),
            last_button: [None, None],
            message: "Hover + single-press: open wheel",
            message_at: Instant::now() }
    }

    fn persist_settings(&self) {
        let Some(path) = &self.settings_path else { return; };
        let settings = format!("v1|{}|{:.0}|{:.0}",
            self.slots.iter().map(usize::to_string).collect::<Vec<_>>().join(","),
            self.size_percent, self.opacity_percent);
        if let Err(error) = std::fs::write(path, settings) {
            log::warn!("Could not save stylus wheel settings: {error}");
        }
    }

    fn scale(&self) -> f32 { self.size_percent / 100.0 }

    fn customize(&mut self, ctx: &Context) {
        if !self.settings_open { return; }
        let mut open = self.settings_open;
        let mut changed = false;
        let customize_response = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("pc-wheel-customize"))
            .open(&mut open)
            .resizable(false)
            .collapsible(false)
            .default_width(320.0)
            .show(ctx, |ui| {
                ui.label("Style: Default  •  8 segments");
                ui.label("Choose a tool for each position. Existing selections swap positions.");
                ui.separator();
                for slot in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", slot + 1));
                        let mut selected = self.slots[slot];
                        egui::ComboBox::from_id_salt(("pc-wheel-slot", slot))
                            .selected_text(LABELS[selected])
                            .width(180.0)
                            .show_ui(ui, |ui| {
                                for i in 0..LABELS.len() {
                                    ui.selectable_value(&mut selected, i, LABELS[i]);
                                }
                            });
                        if selected != self.slots[slot] {
                            if let Some(previous) = self.slots.iter().position(|n| *n == selected) {
                                self.slots[previous] = self.slots[slot];
                            }
                            self.slots[slot] = selected;
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
                    self.size_percent = 100.0;
                    self.opacity_percent = 85.0;
                    changed = true;
                }
                ui.separator();
                ui.label("Actual-size preview appears beside this window.");
                ui.label("75–125% size and opacity match the real Stylus Wheel.");
                ui.label("Pen button: single opens wheel, double selects Eraser.");
            });
        self.settings_open = open;
        if changed { self.persist_settings(); ctx.request_repaint(); }
        // The preview is visual only; never retain an interactive wheel while
        // customization is open.  Keep the normal editor pointer path intact.
        if self.settings_open {
            self.open = false;
            self.single_wait = None;
            self.hover_blocked = false;
            if let Some(response) = customize_response {
                self.preview_actual_size(ctx, response.response.rect);
            }
        }
    }

    fn preview_actual_size(&self, ctx: &Context, dialog: egui::Rect) {
        let screen = ctx.content_rect();
        let size = SIZE * self.scale();
        let margin = 16.0;
        let right_room = screen.right() - dialog.right();
        let left_room = dialog.left() - screen.left();
        let x = if right_room >= size + margin * 2.0 {
            (dialog.right() + screen.right()) * 0.5
        } else if left_room >= size + margin * 2.0 {
            (screen.left() + dialog.left()) * 0.5
        } else {
            screen.center().x
        };
        let center = pos2(
            x.clamp(screen.left() + size * 0.5, (screen.right() - size * 0.5).max(screen.left() + size * 0.5)),
            dialog.center().y.clamp(screen.top() + size * 0.5, (screen.bottom() - size * 0.5).max(screen.top() + size * 0.5)),
        );
        egui::Area::new(Id::new("pc-wheel-full-scale-preview"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                // 1:1 painter, no 0.58 factor; the physical wheel size and
                // alpha precisely match normal operation on this display.
                self.paint_wheel(ui, rect, self.scale(), None);
            });
    }
    /// Exact raster of the user-supplied Pc SVG. Build workflow generates
    /// the transparent RGBA file; no new runtime image decoder is needed.
    fn pc_logo(ctx: &Context) -> egui::TextureHandle {
        let texture_id = Id::new("pc-wheel-user-svg-logo");
        if let Some(existing) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(texture_id)) {
            return existing;
        }
        const PIXELS: &[u8] = include_bytes!("stylus_wheel_pc.rgba");
        const WIDTH: usize = 192;
        const HEIGHT: usize = 120;
        let image = egui::ColorImage::from_rgba_unmultiplied([WIDTH, HEIGHT], PIXELS);
        let texture = ctx.load_texture(
            "photocraft-wheel-user-svg-pc",
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
        self.hover_blocked = false;
        self.single_wait = None;
        self.action = None;
        self.last_button = [None, None];
        self.notify(if enabled { "Wheel ON • hover + single press" } else { "Wheel OFF" });
        ctx.data_mut(|d| d.insert_temp(Id::new("pc_stylus_wheel_enabled"), enabled));
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
                self.action = Some("tools.select.eraser");
                self.notify("Double press • Eraser");
            }
            _ => {}
        }
        ctx.request_repaint();
    }
    fn clamped(position: Pos2, rect: egui::Rect, scale: f32) -> Pos2 {
        let inset = SIZE * scale * 0.5 + 10.0;
        pos2(position.x.clamp(rect.min.x + inset, (rect.max.x - inset).max(rect.min.x + inset)),
             position.y.clamp(rect.min.y + inset, (rect.max.y - inset).max(rect.min.y + inset)))
    }
    fn hit(center: Pos2, pos: Pos2, scale: f32) -> Option<usize> {
        let vector = pos - center;
        if vector.length() < INNER * scale || vector.length() > (R + 11.0) * scale {
            return None;
        }
        Some((((vector.y.atan2(vector.x).to_degrees() + 112.5)
            .rem_euclid(360.0) / 45.0).floor() as usize).min(7))
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        // A settings preview is never a live tool target.  Leave all
        // pointer events untouched for the customization window itself.
        if self.settings_open {
            self.open = false;
            self.single_wait = None;
            self.hover_blocked = false;
            return;
        }
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
        // Android.7 safe path: consume only wheel-owned input. Do NOT install
        // Android.8's global PointerGone filtering or make the wheel Area
        // interactable: both can interfere with the editor's canvas event loop.
        let mut retained = Vec::with_capacity(raw.events.len() + 1);
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerMoved(pos) => {
                    self.hover = Some(pos);
                    let inside = self.open && self.center.is_some_and(|center|
                        (pos - center).length() <= (R + 12.0) * self.scale());
                    if inside {
                        // Clear the underlying egui hover ONCE on entry only.
                        // Repeated PointerGone injections caused a prior ANR
                        // regression and must never run every frame.
                        if !self.hover_blocked {
                            retained.push(egui::Event::PointerGone);
                            self.hover_blocked = true;
                        }
                    } else {
                        self.hover_blocked = false;
                        retained.push(egui::Event::PointerMoved(pos));
                    }
                }
                egui::Event::PointerGone => {
                    self.hover_blocked = false;
                    retained.push(egui::Event::PointerGone);
                }
                egui::Event::Touch { pos, .. } if self.open && self.center.is_some_and(|center|
                    (pos - center).length() <= (R + 12.0) * self.scale()) => {
                    // A touch over an open wheel must not select the image below.
                }
                egui::Event::PointerButton {pos, pressed: true, ..} if self.open => {
                    self.action = self.center.and_then(|center|
                        Self::hit(center, pos, self.scale()))
                        .map(|slot| COMMANDS[self.slots[slot]]);
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
        if pen_down { self.single_wait = None; }
        if let Some((when, point)) = self.single_wait {
            if when.elapsed() >= WAIT {
                self.single_wait = None;
                if let Some(pos) = point.or(self.hover) {
                    self.center = Some(Self::clamped(pos, ctx.content_rect(), self.scale()));
                    self.open = true;
                    self.opened_at = Instant::now();
                    self.notify("Hover to highlight • tap tip to select");
                    ctx.request_repaint();
                } else { self.notify("Hover the pen over the canvas first"); }
            } else {
                ctx.request_repaint_after(WAIT.saturating_sub(when.elapsed()));
            }
        }
        // Wheel can open without a fresh motion event (pen side-button).
        // Clear the previous canvas hover once as soon as it covers that
        // point, then leave the normal Android.7 pointer router untouched.
        if self.open && !self.hover_blocked && self.center.is_some_and(|center|
            self.hover.is_some_and(|pos| (pos - center).length() <= (R + 12.0) * self.scale()))
        {
            raw.events.push(egui::Event::PointerGone);
            self.hover_blocked = true;
        }
        if !self.open { self.hover_blocked = false; }
    }
    pub fn take_action(&mut self) -> Option<&'static str> {
        self.action.take()
    }
    pub fn render(&mut self, ui: &mut Ui) {
        let ctx = ui.ctx().clone();
        self.customize(&ctx);
        if !self.enabled { return; }
        let screen = ctx.content_rect();
        let theme = photocraft_ui_egui::theme::Tokens::get(&ctx);
        // Brief toast: 1.9 seconds visible, then 0.5 seconds fading out.
        let elapsed = self.message_at.elapsed();
        if elapsed < FEEDBACK_HOLD + FEEDBACK_FADE {
            let alpha = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
                1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32() / FEEDBACK_FADE.as_secs_f32()
            };
            let alpha = alpha.clamp(0.0, 1.0);
            if alpha < 1.0 { ctx.request_repaint_after(Duration::from_millis(40)); }
            egui::Area::new(Id::new("pc-wheel-bottom"))
                .order(Order::Foreground)
                .fixed_pos(pos2((screen.center().x - 175.0).max(screen.min.x),
                    screen.max.y - 43.0))
                .interactable(false)
                .show(&ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(350.0, 31.0), Sense::hover());
                    let painter = ui.painter_at(rect);
                    painter.rect_filled(rect, 13.0, Color32::from_rgba_unmultiplied(
                        theme.card.r(), theme.card.g(), theme.card.b(),
                        (244.0 * alpha) as u8));
                    painter.rect_stroke(rect, 13.0,
                        Stroke::new(1.0, theme.field_border.gamma_multiply(alpha)),
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
        let scale = scale * self.scale();
        let size = SIZE * scale;
        let highlighted = self.hover.and_then(|p| Self::hit(center, p, scale));
        let dark = theme.kind.is_dark();
        egui::Area::new(Id::new("pc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(&ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                self.paint_wheel(ui, rect, scale, highlighted);
            });
    }

    // Single painter for the interactive wheel and non-interactive settings preview.
    // Keep the owner's Pc SVG, exact toolbar icons and segment shading identical.
    fn paint_wheel(&self, ui: &mut Ui, rect: egui::Rect, scale: f32, highlighted: Option<usize>) {
        let ctx = ui.ctx().clone();
        let theme = photocraft_ui_egui::theme::Tokens::get(&ctx);
        let dark = theme.kind.is_dark();
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
                        theme.shadow.gamma_multiply(softness),
                    );
                }
                painter.circle_filled(c, R * scale,
                    Color32::from_rgba_unmultiplied(
                        theme.card.r(), theme.card.g(), theme.card.b(),
                        (245.0 * self.opacity_percent / 100.0) as u8));
                for i in 0..8 {
                    let degrees = -90.0 + i as f32 * 45.0;
                    let first = (degrees - 21.5).to_radians();
                    let last = (degrees + 21.5).to_radians();
                    let item = self.slots[i];
                    let mut vertices = vec![c];
                    for step in 0..=16 {
                        let angle = first + (last - first) * step as f32 / 16.0;
                        vertices.push(c + vec2(angle.cos(), angle.sin()) * R * scale);
                    }
                    let active = highlighted == Some(i);
                    let normal = if i % 2 == 0 {
                        Self::mix(theme.card, theme.field, if dark { 0.18 } else { 0.30 })
                    } else {
                        Self::mix(theme.card, theme.field, if dark { 0.68 } else { 0.72 })
                    };
                    let fill = if active {
                        Self::mix(normal, Color32::from_rgb(0, 118, 212), 0.76)
                    } else { normal }.gamma_multiply(self.opacity_percent / 100.0);
                    painter.add(Shape::convex_polygon(vertices, fill,
                        Stroke::new(if active { 1.8 } else { 0.65 },
                            if active { theme.accent }
                            else { theme.field_border.gamma_multiply(0.70) })));
                    let a = degrees.to_radians();
                    let icon_pos = c + vec2(a.cos(), a.sin()) * 87.0 * scale;
                    // Exact official vector icon renderer, shared with the toolbar.
                    // Its SVG is embedded and styled by photocraft_ui_egui::icons.
                    let image_center = icon_pos - vec2(0.0, 10.0) * scale;
                    photocraft_ui_egui::icons::paint(
                        ui,
                        egui::Rect::from_center_size(image_center, vec2(24.0, 24.0) * scale),
                        TOOLBAR_ICONS[item],
                        24.0 * scale,
                        theme.text,
                    );
                    painter.text(icon_pos + vec2(0.0, 13.0),
                        egui::Align2::CENTER_CENTER, LABELS[item],
                        FontId::proportional(11.0), theme.text_dim);
                }
                painter.circle_stroke(c, R * scale,
                    Stroke::new(0.8, theme.field_border.gamma_multiply(0.58)));
                // Full user-selected round hub, no square tile.
                // The exact uploaded SVG paths are shown here as a texture,
                // retaining the author's original cyan #27a5de letterforms.
                let hub_navy = Color32::from_rgb(0, 28, 49);
                let hub_cyan = Color32::from_rgb(0, 180, 246);
                painter.circle_filled(c, (INNER + 2.0) * scale, hub_navy);
                painter.circle_stroke(c, (INNER + 2.0) * scale,
                    Stroke::new(1.3, hub_cyan));
                let pc = Self::pc_logo(&ctx);
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
                    highlighted.map(|i| LABELS[self.slots[i]]).unwrap_or(WHEEL_STYLE),
                    FontId::proportional(11.0 * scale), Color32::WHITE);
    }
}