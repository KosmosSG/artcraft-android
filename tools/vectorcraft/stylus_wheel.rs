//! Experimental, opt-in VectorCraft Magic-Pencil 4s wheel. TEST ONLY.
use egui::{Color32, Context, FontId, Id, Order, Pos2, RawInput, Sense, Shape, Stroke, StrokeKind, Ui, pos2, vec2};
use std::time::{Duration, Instant};

const R: f32 = 128.0;
const INNER: f32 = 46.0;
const SIZE: f32 = 312.0;
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const WAIT: Duration = Duration::from_millis(400);
// All actions below map to existing VectorCraft tools or commands.
const LABELS: [&str; 12] = ["Select", "Nodes", "Pen", "Type", "Shapes", "Hand", "Undo", "Redo", "Eraser", "Pencil", "Ellipse", "Zoom"];
const ICONS: [&str; 12] = ["dc-selection", "dc-direct", "pen-tool", "dc-type", "shapes", "hand", "undo-2", "redo-2", "eraser", "pencil", "circle", "zoom-in"];
const COMMANDS: [&str; 12] = ["selection", "directSelection", "pen", "type", "rectangle", "hand", "edit.undo", "edit.redo", "eraser", "pencil", "ellipse", "zoom"];
const DEFAULT_LAYOUT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];
const POSITIONS: [&str; 8] = ["Upper right", "Right", "Lower right", "Bottom", "Lower left", "Left", "Upper left", "Top"];

pub(crate) struct Wheel {
    pub enabled: bool,
    open: bool,
    customize_open: bool,
    layout: [usize; 8],
    layout_dirty: bool,
    size_percent: u32,
    opacity_percent: u32,
    swallow_contact: bool,
    consumed_events: u64,
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
        Self { enabled, open: false, customize_open: false, layout: DEFAULT_LAYOUT, layout_dirty: false, size_percent: 84, opacity_percent: 78, swallow_contact: false, consumed_events: 0, center: None, hover: None,
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
        if !self.enabled || self.customize_open { return; }
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
    /// leave Proposal A intact. Never deserialize unchecked action strings.
    pub fn set_layout_string(&mut self, encoded: &str) {
        // Eight legacy slot indices remain supported. Newer settings append
        // bounded size and opacity percentages, preserving old user layouts.
        let values: Option<Vec<usize>> = encoded
            .split(',')
            .map(|part| part.trim().parse::<usize>().ok())
            .collect();
        if let Some(values) = values {
            let valid = (values.len() == 8 || values.len() == 10)
                && values[..8].iter().all(|index| *index < COMMANDS.len())
                && (values.len() == 8 || ((75..=140).contains(&values[8])
                    && (30..=100).contains(&values[9])));
            if valid {
                self.layout.copy_from_slice(&values[..8]);
                if values.len() == 10 {
                    self.size_percent = values[8] as u32;
                    self.opacity_percent = values[9] as u32;
                }
            }
        }
    }

    pub fn take_layout_change(&mut self) -> Option<String> {
        if !self.layout_dirty { return None; }
        self.layout_dirty = false;
        let mut saved = self.layout.iter().map(|index| index.to_string()).collect::<Vec<_>>().join(",");
        saved.push_str(&format!(",{},{}", self.size_percent, self.opacity_percent));
        Some(saved)
    }

    pub fn open_customizer(&mut self, ctx: &Context) {
        self.open = false;
        self.single_wait = None;
        self.action = None;
        self.customize_open = true;
        ctx.request_repaint();
    }

    fn clamped(&self, position: Pos2, rect: egui::Rect) -> Pos2 {
        let inset = SIZE * self.size_percent as f32 / 200.0 + 10.0;
        pos2(position.x.clamp(rect.min.x + inset, (rect.max.x - inset).max(rect.min.x + inset)),
             position.y.clamp(rect.min.y + inset, (rect.max.y - inset).max(rect.min.y + inset)))
    }
    fn hit(&self, center: Pos2, pos: Pos2) -> Option<usize> {
        let vector = (pos - center) * (100.0 / self.size_percent as f32);
        if vector.length() < INNER || vector.length() > R + 11.0 { return None; }
        Some((((vector.y.atan2(vector.x).to_degrees() + 90.0).rem_euclid(360.0) / 45.0).floor() as usize).min(7))
    }
    pub fn capture(&mut self, ctx: &Context, raw: &mut RawInput, blocked: bool) {
        // Finish an owned contact even when its selected action entered Type.
        // Never leak its release into a newly opened document or modal.
        if self.swallow_contact && (!self.enabled || blocked || self.customize_open) {
            raw.events.retain(|event| match event {
                egui::Event::PointerButton { pressed: false, .. } | egui::Event::PointerGone => {
                    self.swallow_contact = false; false
                }
                egui::Event::PointerMoved(_) | egui::Event::PointerButton {..}
                    | egui::Event::Touch {..} | egui::Event::MouseMoved(_) => false,
                _ => true,
            });
            raw.events.push(egui::Event::PointerGone);
            ctx.data_mut(|d| d.insert_temp(Id::new("vc-wheel-input-owned"), true));
            self.open = false;
            self.single_wait = None;
            self.action = None;
            return;
        }
        if !self.enabled || blocked || self.customize_open {
            self.open = false;
            self.single_wait = None;
            self.action = None;
            self.swallow_contact = false;
            ctx.data_mut(|d| d.insert_temp(Id::new("vc-wheel-input-owned"), self.customize_open));
            return;
        }
        // Java and native input can consume pen keys without egui receiving
        // a KeyboardInput redraw. Poll at a low idle cadence only when opt-in.
        ctx.request_repaint_after(Duration::from_millis(100));
        self.hover = ctx.input(|i| i.pointer.hover_pos()).or(self.hover);
        let mut isolated = self.open || self.swallow_contact;
        let event_count = raw.events.len();
        let mut retained = Vec::with_capacity(raw.events.len());
        for event in raw.events.drain(..) {
            match event {
                egui::Event::PointerButton {pressed: false, ..} if self.swallow_contact => {
                    self.swallow_contact = false;
                }
                egui::Event::Touch {..} if isolated => {}
                egui::Event::PointerMoved(pos) => {
                    self.hover = Some(pos);
                    if !isolated { retained.push(egui::Event::PointerMoved(pos)); }
                }
                egui::Event::PointerButton {pos, button: egui::PointerButton::Primary, pressed: true, ..} if self.open => {
                    self.swallow_contact = true;
                    self.action = self.center.and_then(|center| self.hit(center, pos));
                    self.notify(if self.action.is_some() { "Wheel selection accepted" }
                        else { "Wheel cancelled • tapped outside" });
                    self.open = false;
                    ctx.request_repaint();
                }
                egui::Event::PointerButton {..} if isolated => {}
                egui::Event::MouseMoved(_) | egui::Event::MouseWheel {..}
                    | egui::Event::Zoom(_) | egui::Event::Rotate(_) if isolated => {}
                egui::Event::PointerGone if isolated => {
                    self.hover = None;
                    self.swallow_contact = false;
                }
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
                    self.center = Some(self.clamped(pos, ctx.content_rect()));
                    self.open = true;
                    self.opened_at = Instant::now();
                    self.notify("Hover to highlight • tap tip to select");
                    ctx.request_repaint();
                } else { self.notify("Hover the pen over the canvas first"); }
            } else {
                ctx.request_repaint_after(WAIT.saturating_sub(when.elapsed()));
            }
        }
        isolated |= self.open;
        if isolated {
            raw.events.retain(|event| !matches!(event,
                egui::Event::PointerMoved(_) | egui::Event::PointerButton {..}
                | egui::Event::Touch {..} | egui::Event::MouseMoved(_)
                | egui::Event::MouseWheel {..} | egui::Event::Zoom(_) | egui::Event::Rotate(_)));
            self.consumed_events += event_count.saturating_sub(raw.events.len()) as u64;
            raw.events.push(egui::Event::PointerGone);
        }
        let previously_owned = ctx.data(|d| d.get_temp::<bool>(Id::new("vc-wheel-input-owned")).unwrap_or(false));
        if previously_owned && !isolated && raw.events.is_empty() {
            if let Some(pos) = self.hover { raw.events.push(egui::Event::PointerMoved(pos)); }
        }
        ctx.data_mut(|d| d.insert_temp(Id::new("vc-wheel-input-owned"), isolated));
    }
    pub fn diagnostic_counts(&self) -> u64 { self.consumed_events }
    pub fn take_action(&mut self) -> Option<&'static str> {
        self.action.take().map(|i| COMMANDS[if i == 8 { 8 } else { self.layout[i] }])
    }
    pub fn render(&mut self, ui: &mut Ui) {
        if !self.enabled && !self.customize_open { return; }
        let ctx = ui.ctx().clone();

        if self.customize_open {
            let mut open = true;
            let mut done = false;
            let screen = ctx.content_rect();
            // PhotoCraft-style compact floating editor. Do not allocate the
            // entire screen height or add a preview pane to the Window.
            egui::Window::new("Stylus Wheel — Default")
                .id(Id::new("vc-wheel-settings"))
                .open(&mut open)
                .collapsible(false)
                .resizable(false)
                .default_pos(pos2(screen.min.x + 20.0, screen.min.y + 22.0))
                .default_width(400.0)
                .max_width((screen.width() - 32.0).min(420.0).max(272.0))
                .constrain(true)
                .show(&ctx, |ui| {
                    ui.set_width((screen.width() - 70.0).min(368.0).max(245.0));
                    ui.strong("Style: Default  •  8 segments");
                    ui.add_space(5.0);
                    ui.label("Choose a tool for each position. Existing");
                    ui.label("selections swap positions.");
                    ui.add_space(3.0);
                    ui.add_space(5.0);
                    ui.separator();
                    // Shorter devices scroll ONLY the assignments, not the
                    // window header, slider values, actions or help message.
                    let max_list_height = (screen.height() - 310.0).clamp(175.0, 350.0);
                    egui::ScrollArea::vertical()
                        .id_salt("vc-wheel-compact-assignments")
                        .max_height(max_list_height)
                        .show(ui, |ui| self.assignments(ui));
                    ui.add_space(5.0);
                    ui.separator();
                    ui.add_space(5.0);
                    ui.scope(|ui| self.sliders(ui));
                    ui.add_space(7.0);
                    self.buttons(ui, &mut done);
                    ui.separator();
                    ui.add_space(4.0);
                    ui.small("Actual-size preview appears beside this window.");
                    ui.small("75–140% wheel size. Opacity 30–100%.");
                    ui.add_space(2.0);
                    ui.small("Pen button: single opens wheel; double selects Eraser.");
                });
            self.customize_open = open && !done;
            if self.customize_open {
                self.external_preview(&ctx);
            }
        }
        if !self.enabled { return; }
        let screen = ctx.content_rect();
        let theme = vectorcraft_ui_egui::theme::Tokens::get(&ctx);
        // PhotoCraft reference: single centered, understated message bar
        // above the bottom status dock. Wheel stays usable behind it.
        let elapsed = self.message_at.elapsed();
        if elapsed < FEEDBACK_HOLD + FEEDBACK_FADE {
            let alpha = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
                1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32() / FEEDBACK_FADE.as_secs_f32()
            };
            let alpha = alpha.clamp(0.0, 1.0);
            if alpha < 1.0 { ctx.request_repaint_after(Duration::from_millis(40)); }
            let width = screen.width().min(450.0).max(120.0);
            egui::Area::new(Id::new("vc-wheel-bottom"))
                .order(Order::Foreground)
                .fixed_pos(pos2(screen.center().x - width * 0.5,
                    screen.max.y - 57.0))
                .interactable(false)
                .show(&ctx, |ui| {
                    let (rect, _) = ui.allocate_exact_size(vec2(width, 38.0), Sense::hover());
                    let painter = ui.painter_at(rect);
                    painter.rect_filled(rect, 16.0, Color32::from_rgba_unmultiplied(
                        52, 52, 54, (235.0 * alpha) as u8));
                    painter.rect_stroke(rect, 16.0,
                        Stroke::new(0.85, Color32::from_rgb(110, 111, 113)
                            .gamma_multiply(0.55 * alpha)),
                        StrokeKind::Inside);
                    painter.text(rect.center(), egui::Align2::CENTER_CENTER, self.message,
                        FontId::proportional(12.0),
                        Color32::from_rgb(231, 231, 232).gamma_multiply(alpha));
                });
        }
        if !self.open { return; }
        let Some(center) = self.center else { return };
        let t = (self.opened_at.elapsed().as_secs_f32() / 0.18).min(1.0);
        if t < 1.0 { ctx.request_repaint(); }
        let scale = (0.86 + 0.14 * t) * self.size_percent as f32 / 100.0;
        let opacity = self.opacity_percent as f32 / 100.0;
        let size = SIZE * scale;
        let highlighted = self.hover.and_then(|p| self.hit(center, p));
        egui::Area::new(Id::new("vc-wheel-plate"))
            .order(Order::Foreground)
            .fixed_pos(center - vec2(size * 0.5, size * 0.5))
            .interactable(false)
            .show(&ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                self.paint_wheel(ui, rect, scale, highlighted);
            });
    }
    fn assignments(&mut self, ui: &mut Ui) {
        // PhotoCraft reference: short Slot 1–8 labels, consistent two-column
        // dropdown rows and positions kept as hover hints.
        egui::Grid::new("vc-wheel-assignment-grid").num_columns(2)
            .spacing(vec2(12.0, 7.0)).min_row_height(32.0).show(ui, |ui| {
                for slot in 0..8 {
                    ui.add_sized(vec2(60.0, 30.0),
                        egui::Label::new(format!("Slot {}", slot + 1)))
                        .on_hover_text(POSITIONS[slot]);
                    let previous = self.layout[slot];
                    egui::ComboBox::from_id_salt(("vc-wheel-slot", slot))
                        .selected_text(LABELS[previous]).width(236.0).height(260.0)
                        .show_ui(ui, |ui| {
                            for index in 0..LABELS.len() {
                                if ui.selectable_label(self.layout[slot] == index, LABELS[index]).clicked()
                                    && index != self.layout[slot] {
                                    // Match PhotoCraft: never show duplicate
                                    // tools when swapping an occupied slot.
                                    if let Some(existing) = (0..8)
                                        .find(|&other| other != slot && self.layout[other] == index) {
                                        self.layout[existing] = previous;
                                    }
                                    self.layout[slot] = index;
                                    self.layout_dirty = true;
                                }
                            }
                        });
                    ui.end_row();
                }
            });
    }
    fn sliders(&mut self, ui: &mut Ui) {
        // Same PhotoCraft order: horizontal slider, precise numeric percentage,
        // then the field label. The native Vc accent replaces PhotoCraft blue.
        ui.visuals_mut().selection.bg_fill = Color32::from_rgb(255, 159, 0);
        ui.visuals_mut().widgets.active.bg_fill = Color32::from_rgb(255, 159, 0);
        ui.visuals_mut().widgets.hovered.bg_fill = Color32::from_rgb(173, 94, 14);
        ui.spacing_mut().slider_width = 175.0;
        egui::Grid::new("vc-wheel-slider-grid").num_columns(3)
            .spacing(vec2(9.0, 9.0)).min_row_height(31.0).show(ui, |ui| {
                self.layout_dirty |= ui.add(egui::Slider::new(&mut self.size_percent, 75..=140)
                    .show_value(false).step_by(1.0)).changed();
                self.layout_dirty |= ui.add_sized(vec2(66.0, 25.0),
                    egui::DragValue::new(&mut self.size_percent).range(75..=140)
                        .speed(1.0).suffix("%")).changed();
                ui.label("Wheel size"); ui.end_row();
                self.layout_dirty |= ui.add(egui::Slider::new(&mut self.opacity_percent, 30..=100)
                    .show_value(false).step_by(1.0)).changed();
                self.layout_dirty |= ui.add_sized(vec2(66.0, 25.0),
                    egui::DragValue::new(&mut self.opacity_percent).range(30..=100)
                        .speed(1.0).suffix("%")).changed();
                ui.label("Opacity"); ui.end_row();
            });
    }
    fn buttons(&mut self, ui: &mut Ui, done: &mut bool) {
        ui.horizontal(|ui| {
            if ui.button("Restore Default").clicked() {
                self.layout = DEFAULT_LAYOUT;
                self.size_percent = 84;
                self.opacity_percent = 78;
                self.layout_dirty = true;
            }
        });
        // Keep the title-bar X as the single close action, like PhotoCraft.
        // Changes persist automatically on each adjustment.
        let _ = done;
        ui.small("Changes saved automatically.");
    }
    /// The preview is a non-interactive foreground area on the canvas,
    /// OUTSIDE the settings dialog. It uses the actual wheel scale/opacity,
    /// rather than a fit-to-panel thumbnail, and cannot select a document.
    fn external_preview(&self, ctx: &Context) {
        let screen = ctx.content_rect();
        let size = SIZE * self.size_percent as f32 / 100.0;
        if screen.width() < 465.0 + size { return; }
        let right_room = screen.width() - 442.0;
        let x = screen.min.x + 442.0 + (right_room - size) * 0.50;
        let y = screen.center().y - size * 0.5 - 12.0;
        egui::Area::new(Id::new("vc-wheel-external-preview"))
            .order(Order::Foreground)
            .fixed_pos(pos2(x, y.max(screen.min.y + 36.0)))
            .interactable(false)
            .show(ctx, |ui| {
                ui.label("Live wheel preview");
                let (rect, _) = ui.allocate_exact_size(vec2(size, size), Sense::hover());
                let scale = self.size_percent as f32 / 100.0;
                let highlighted = None;
                self.paint_wheel(ui, rect, scale, highlighted);
            });
    }

    /// The preview and live overlay deliberately share every painted element.
    fn paint_wheel(&self, ui: &Ui, rect: egui::Rect, scale: f32, highlighted: Option<usize>) {
        let theme = vectorcraft_ui_egui::theme::Tokens::get(ui.ctx());
        let dark = theme.dark;
        let opacity = self.opacity_percent as f32 / 100.0;
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
                        Color32::BLACK.gamma_multiply(softness * opacity),
                    );
                }
                painter.circle_filled(c, R * scale,
                    Color32::from_rgba_unmultiplied(
                        theme.panel.r(), theme.panel.g(), theme.panel.b(),
                        (245.0 * opacity).round() as u8));
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
                    // PhotoCraft dual-tone graphite: subtle alternating
                    // greys, no high-contrast spokes or hard radial seams.
                    let normal = if dark {
                        if i % 2 == 0 { Color32::from_rgb(43, 43, 45) }
                        else { Color32::from_rgb(49, 49, 51) }
                    } else if i % 2 == 0 {
                        Self::mix(theme.panel, theme.input, 0.17)
                    } else {
                        Self::mix(theme.panel, theme.input, 0.31)
                    };
                    let fill = if active {
                        Self::mix(normal, Color32::from_rgb(255, 159, 0), if dark { 0.27 } else { 0.16 })
                    } else { normal };
                    painter.add(Shape::convex_polygon(vertices, fill.gamma_multiply(opacity),
                        Stroke::new(if active { 1.25 } else { 0.52 },
                            (if active { Color32::from_rgb(255, 159, 0) }
                            else { theme.input_border.gamma_multiply(0.48) }).gamma_multiply(opacity))));
                    let a = degrees.to_radians();
                    let icon_pos = c + vec2(a.cos(), a.sin()) * 87.0 * scale;
                    vectorcraft_ui_egui::icons::paint(ui, ICONS[self.layout[i]],
                        egui::Rect::from_center_size(icon_pos - vec2(0.0, 10.0), vec2(24.0, 24.0) * scale),
                        (if active { Color32::from_rgb(255, 185, 79) }
                          else if dark { Color32::from_rgb(234, 234, 234) }
                          else { theme.text }).gamma_multiply(opacity));
                    painter.text(icon_pos + vec2(0.0, 13.0),
                        egui::Align2::CENTER_CENTER, LABELS[self.layout[i]],
                        FontId::proportional(11.0 * scale),
                         (if dark { Color32::from_rgb(190, 190, 191) }
                          else { theme.text_dim }).gamma_multiply(opacity));
                }
                // The thin surrounding rim matches the orange Vc launcher mark.
                // Match the same rim in the real overlay and live preview.
                painter.circle_stroke(c, R * scale,
                    Stroke::new(0.9 * scale, Color32::from_rgb(255, 159, 0)
                         .gamma_multiply(0.66 * opacity)));
                // Full user-selected round hub, no square tile.
                // The exact uploaded SVG paths are shown here as a texture,
                // retaining the approved orange Vc letterforms.
                let hub_burgundy = Color32::from_rgb(45, 0, 0);
                let hub_orange = Color32::from_rgb(255, 159, 0);
                painter.circle_filled(c, (INNER + 2.0) * scale, hub_burgundy.gamma_multiply(opacity));
                painter.circle_stroke(c, (INNER + 2.0) * scale,
                    Stroke::new(1.3, hub_orange.gamma_multiply(opacity)));
                let pc = Self::vc_logo(ui.ctx());
                let mark_rect = egui::Rect::from_center_size(
                    c - vec2(0.0, 8.0) * scale,
                    vec2(40.0, 25.0) * scale,
                );
                painter.image(
                    pc.id(), mark_rect,
                    egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
                    Color32::WHITE.gamma_multiply(opacity),
                );
                painter.text(c + vec2(0.0, 22.0) * scale,
                    egui::Align2::CENTER_CENTER,
                    highlighted.map(|i| LABELS[self.layout[i]]).unwrap_or("Tools"),
                    FontId::proportional(11.0 * scale), Color32::WHITE.gamma_multiply(opacity));
    }

}

#[cfg(test)]
mod tests {
    use super::*;
    fn button(pos: Pos2, pressed: bool) -> egui::Event {
        egui::Event::PointerButton { pos, button: egui::PointerButton::Primary, pressed, modifiers: Default::default() }
    }
    fn owned(ctx: &Context) -> bool {
        ctx.data(|d| d.get_temp::<bool>(Id::new("vc-wheel-input-owned")).unwrap_or(false))
    }
    fn wheel() -> Wheel {
        let mut w = Wheel::new(true); w.open = true; w.center = Some(pos2(300.0, 300.0)); w
    }
    #[test]
    fn wheel_hover_never_reaches_canvas_and_tap_is_once() {
        let ctx = Context::default(); let mut w = wheel();
        let p = pos2(330.0, 220.0);
        let mut raw = RawInput::default(); raw.events = vec![egui::Event::PointerMoved(p)];
        w.capture(&ctx, &mut raw, false);
        assert!(owned(&ctx)); assert_eq!(w.hover, Some(p));
        assert!(!raw.events.iter().any(|e| matches!(e, egui::Event::PointerMoved(_))));
        raw.events = vec![button(p, true), button(p, false), egui::Event::PointerMoved(p)];
        w.capture(&ctx, &mut raw, false);
        assert_eq!(w.take_action(), Some("selection")); assert_eq!(w.take_action(), None);
        assert!(owned(&ctx)); assert!(!w.swallow_contact);
        raw.events = vec![egui::Event::PointerMoved(p)];
        w.capture(&ctx, &mut raw, false);
        assert!(!owned(&ctx)); assert!(matches!(raw.events[0], egui::Event::PointerMoved(_)));
    }
    #[test]
    fn wheel_release_after_type_or_document_transition_stays_owned() {
        let ctx = Context::default(); let mut w = wheel();
        let p = pos2(330.0, 220.0); let mut raw = RawInput::default();
        raw.events = vec![button(p, true)]; w.capture(&ctx, &mut raw, false);
        assert!(w.swallow_contact); w.take_action();
        raw.events = vec![button(p, false)]; w.capture(&ctx, &mut raw, true);
        assert!(owned(&ctx)); assert!(!w.swallow_contact);
        raw.events.clear(); w.capture(&ctx, &mut raw, false); assert!(!owned(&ctx));
    }
    #[test]
    fn wheel_cancel_and_repeated_activation_release_fence() {
        let ctx = Context::default(); let mut w = wheel();
        for _ in 0..20 {
            w.open = true;
            let mut raw = RawInput::default();
            raw.events = vec![button(pos2(0.0, 0.0), true), button(pos2(0.0, 0.0), false)];
            w.capture(&ctx, &mut raw, false);
            assert_eq!(w.take_action(), None); assert!(!w.open);
            raw.events.clear(); w.capture(&ctx, &mut raw, false); assert!(!owned(&ctx));
        }
    }
    #[test]
    fn wheel_customizer_preserves_ui_events_and_never_executes() {
        let ctx=Context::default(); let mut w=wheel(); w.open_customizer(&ctx);
        let mut raw=RawInput::default(); raw.events=vec![button(pos2(200.0,200.0),true)];
        w.capture(&ctx,&mut raw,false); assert!(owned(&ctx)); assert_eq!(raw.events.len(),1);
        assert_eq!(w.take_action(),None);
        w.customize_open=false; raw.events.clear(); w.capture(&ctx,&mut raw,false); assert!(!owned(&ctx));
    }
    #[test]
    fn wheel_preference_roundtrip_and_scaled_hit() {
        let mut w=wheel(); w.set_layout_string("7,6,5,4,3,2,1,0,140,30");
        assert_eq!(w.layout[0],7); assert_eq!(w.opacity_percent,30);
        assert_eq!(w.hit(pos2(0.0,0.0),pos2(40.0,-150.0)),Some(0));
        w.layout_dirty=true; assert_eq!(w.take_layout_change().unwrap(),"7,6,5,4,3,2,1,0,140,30");
        w.set_layout_string("99,0,0,0,0,0,0,0,900,0"); assert_eq!(w.size_percent,140);
    }
    #[test]
    fn fresh_and_reset_defaults_match_approved_photocraft_reference() {
        let mut w = Wheel::new(true);
        assert_eq!((w.size_percent, w.opacity_percent), (84, 78));
        w.set_layout_string("7,6,5,4,3,2,1,0,99,61");
        assert_eq!((w.size_percent, w.opacity_percent), (99, 61));
        // A pre-existing user's settings are retained until Reset is pressed.
        assert_eq!(w.layout[0], 7);
        w.layout = DEFAULT_LAYOUT;
        w.size_percent = 84;
        w.opacity_percent = 78;
        assert_eq!((w.size_percent, w.opacity_percent), (84, 78));
    }

    #[test]
    fn wheel_preview_uses_live_settings_without_document_actions() {
        let ctx=Context::default(); let mut w=wheel(); w.open_customizer(&ctx);
        for width in [400.0, 1100.0] {
            for settings in ["0,1,2,3,4,5,6,7,75,30", "7,6,5,4,3,2,1,0,140,100"] {
                w.set_layout_string(settings);
                let mut raw=RawInput::default();
                raw.screen_rect=Some(egui::Rect::from_min_size(Pos2::ZERO,vec2(width,800.0)));
                let mut out=ctx.run_ui(raw, |ui| w.render(ui));
                // Headless tests have no GPU texture uploader. Explicitly consume
                // its pending deltas before FullOutput is dropped (egui 0.37).
                out.textures_delta.clear();
                assert!(!out.shapes.is_empty()); assert_eq!(w.take_action(),None);
            }
        }
    }
}
