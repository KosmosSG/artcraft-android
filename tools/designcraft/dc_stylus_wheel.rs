//! DesignCraft-specific Android stylus wheel. Isolated test candidate.
//! Reuses Storytold's toolbar icon painter; never modifies the document on hover.
use egui::{Align2, Color32, Context, FontId, Id, Order, Pos2, Rect, Sense, Shape, Stroke, Ui, pos2, vec2};
use std::{f32::consts::{PI, TAU}, fs, path::PathBuf, time::{Duration, Instant}};

const BG: Color32 = Color32::from_rgb(67, 8, 31);   // Owner supplied Dc icon: #43081F.
const ACCENT: Color32 = Color32::from_rgb(236, 72, 105); // #EC4869.
const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);
const FEEDBACK_FADE: Duration = Duration::from_millis(500);
const ITEMS: [(&str, &str, &str); 14] = [
    ("Select", "tool-selection", "selection"),
    ("Pen", "tool-pen", "pen"),
    ("Shapes", "wheel-shapes", "rectangle"),
    ("Text", "tool-type", "type"),
    ("Layers", "panel-layers", "window.panel"),
    ("Hand", "tool-hand", "hand"),
    ("Redo", "wheel-redo", "edit.redo"),
    ("Undo", "wheel-undo", "edit.undo"),
    ("Pencil", "tool-pencil", "pencil"),
    ("Zoom", "tool-zoom", "zoom"),
    ("Direct Select", "tool-direct", "directSelection"),
    ("Frame", "tool-rect-frame", "rectangleFrame"),
    ("Scale", "tool-scale", "scale"),
    ("Line", "tool-line", "line"),
];
const DEFAULT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];

#[derive(Clone)]
struct Wheel {
    enabled: bool,
    settings_open: bool,
    open: bool,
    center: Pos2,
    slots: [usize; 8],
    size: f32,
    opacity: f32,
    path: Option<PathBuf>,
    last_device_scan: Option<Instant>,
    feedback_message: &'static str,
    feedback_at: Option<Instant>,
}

impl Wheel {
    fn load(ctx: &Context) -> Self {
        let path = std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".config/designcraft-stylus-wheel.v1"));
        let mut wheel = Self {
            enabled: false, settings_open: false, open: false,
            center: ctx.content_rect().center(), slots: DEFAULT,
            size: 75.0, opacity: 100.0, path, last_device_scan: None,
            feedback_message: "", feedback_at: None
        };
        if let Some(text) = wheel.path.as_ref().and_then(|p| fs::read_to_string(p).ok()) {
            let parts: Vec<&str> = text.trim().split('|').collect();
            if parts.len() == 5 && parts[0] == "v1" {
                wheel.enabled = parts[1] == "1";
                if let Ok(n) = parts[2].parse::<f32>() {
                    if n.is_finite() { wheel.size = n.clamp(75.0, 125.0); }
                }
                if let Ok(n) = parts[3].parse::<f32>() {
                    if n.is_finite() { wheel.opacity = n.clamp(60.0, 100.0); }
                }
                let values: Vec<usize> = parts[4].split(',').filter_map(|s| s.parse().ok()).collect();
                if values.len() == 8 && values.iter().all(|n| *n < ITEMS.len())
                    && values.iter().enumerate().all(|(i, n)| !values[..i].contains(n)) {
                    wheel.slots.copy_from_slice(&values);
                }
            }
        }
        wheel
    }

    fn persist(&self) {
        let Some(path) = &self.path else { return; };
        let Some(parent) = path.parent() else { return; };
        if fs::create_dir_all(parent).is_err() { return; }
        let s = format!("v1|{}|{:.0}|{:.0}|{}\n",
            u8::from(self.enabled), self.size, self.opacity,
            self.slots.iter().map(usize::to_string).collect::<Vec<_>>().join(","));
        let temp = path.with_extension("tmp");
        if fs::write(&temp, s).is_ok() {
            if let Err(error) = fs::rename(temp, path) {
                eprintln!("DesignCraft wheel: unable to save settings: {error}");
            }
        }
    }

    fn radius(&self) -> f32 { 152.0 * self.size / 100.0 }
    fn clamp_center(&mut self, ctx: &Context, wanted: Pos2) {
        let screen = ctx.content_rect();
        let r = self.radius() + 8.0;
        let lo_x = screen.left() + r;
        let hi_x = (screen.right() - r).max(lo_x);
        let lo_y = screen.top() + r;
        let hi_y = (screen.bottom() - r).max(lo_y);
        self.center = pos2(wanted.x.clamp(lo_x, hi_x), wanted.y.clamp(lo_y, hi_y));
    }

    fn hit(&self, pointer: Pos2) -> Option<usize> {
        let delta = pointer - self.center;
        let distance = delta.length();
        let r = self.radius();
        if !(r * 0.32..=r).contains(&distance) { return None; }
        let angle = (delta.y.atan2(delta.x) + PI / 2.0 + PI / 8.0).rem_euclid(TAU);
        Some(((angle / (TAU / 8.0)).floor() as usize).min(7))
    }

    fn alpha(&self) -> u8 { (self.opacity * 2.55).round().clamp(0.0, 255.0) as u8 }

    fn notify(&mut self, message: &'static str) {
        self.feedback_message = message;
        self.feedback_at = Some(Instant::now());
    }

    /// PhotoCraft-style bottom-centred status pill: 1.9s hold, 0.5s fade.
    /// Visual-only overlay; it never steals stylus, touch or trackpad events.
    fn paint_feedback(&self, ctx: &Context) {
        let Some(started) = self.feedback_at else { return; };
        let elapsed = started.elapsed();
        if elapsed >= FEEDBACK_HOLD + FEEDBACK_FADE { return; }
        let opacity = if elapsed <= FEEDBACK_HOLD { 1.0 } else {
            1.0 - (elapsed - FEEDBACK_HOLD).as_secs_f32()
                / FEEDBACK_FADE.as_secs_f32()
        }.clamp(0.0, 1.0);
        let screen = ctx.content_rect();
        let width = 350.0f32.min((screen.width() - 24.0).max(80.0));
        let height = 31.0;
        let x = screen.center().x - width * 0.5;
        let y = (screen.bottom() - height - 12.0).max(screen.top());
        egui::Area::new(Id::new("dc-wheel-bottom-feedback"))
            .order(Order::Foreground)
            .fixed_pos(pos2(x, y))
            .interactable(false)
            .show(ctx, |ui| {
                let (rect, _) = ui.allocate_exact_size(vec2(width, height), Sense::hover());
                let painter = ui.painter_at(rect);
                painter.rect_filled(rect, 13.0,
                    Color32::from_rgba_unmultiplied(
                        49, 49, 51, (244.0 * opacity) as u8));
                painter.rect_stroke(rect, 13.0,
                    Stroke::new(1.0, Color32::from_rgba_unmultiplied(
                        105, 105, 109, (135.0 * opacity) as u8)),
                    egui::StrokeKind::Inside);
                painter.text(rect.center(), Align2::CENTER_CENTER, self.feedback_message,
                    FontId::proportional(11.0),
                    Color32::WHITE.gamma_multiply(opacity));
            });
        // No redraws after the temporary notification disappears.
        ctx.request_repaint_after(Duration::from_millis(50));
    }

    fn original_dc_logo(ctx: &Context) -> egui::TextureHandle {
        let id = Id::new("designcraft-wheel-exact-launcher-lettermark");
        if let Some(texture) = ctx.data(|d| d.get_temp::<egui::TextureHandle>(id)) {
            return texture;
        }
        let rgba = include_bytes!("dc_wheel_mark.rgba");
        let pixels = egui::ColorImage::from_rgba_unmultiplied([192, 120], rgba);
        let texture = ctx.load_texture("DesignCraft approved Dc lettering", pixels, egui::TextureOptions::LINEAR);
        ctx.data_mut(|d| d.insert_temp(id, texture.clone()));
        texture
    }

    fn wheel_icon(p: &egui::Painter, rect: Rect, icon: &str) {
        // Unified 24-point pictograms. The wheel has the same icon geometry,
        // line weight and white tint regardless of segment orientation.
        let center = rect.center();
        let half = rect.width().min(rect.height()) * 0.5;
        let at = |x: f32, y: f32| center + vec2(x * half, y * half);
        let stroke = Stroke::new((half * 0.15).clamp(1.8, 2.3), Color32::WHITE);
        let line = |points: &[(f32, f32)]| {
            p.add(Shape::line(
                points.iter().map(|&(x, y)| at(x, y)).collect(),
                stroke,
            ));
        };
        match icon {
            "tool-selection" => {
                // Image 1: clear monoline pointer, not an uneven filled cursor.
                p.add(Shape::closed_line(vec![
                    at(-0.60, -0.92), at(-0.51, 0.73),
                    at(-0.14, 0.34), at(0.22, 0.89),
                    at(0.53, 0.68), at(0.18, 0.15),
                    at(0.76, 0.06),
                ], stroke));
            }
            "tool-pen" => {
                // Symmetric fountain pen nib with a distinct ink breather.
                line(&[
                    (0.0, -0.89), (0.60, -0.12), (0.25, 0.77),
                    (-0.25, 0.77), (-0.60, -0.12), (0.0, -0.89),
                ]);
                line(&[(0.0, -0.89), (0.0, -0.21)]);
                p.circle_stroke(at(0.0, 0.04), half * 0.12, stroke);
            }
            "wheel-shapes" => {
                // Clean two-shape motif; remove the extraneous little triangle.
                p.rect_stroke(
                    Rect::from_min_max(at(-0.78, -0.72), at(0.17, 0.23)),
                    0.4, stroke, egui::StrokeKind::Middle,
                );
                p.circle_stroke(at(0.34, 0.31), half * 0.43, stroke);
            }
            "tool-type" => {
                line(&[(-0.76, -0.72), (0.76, -0.72)]);
                line(&[(0.0, -0.72), (0.0, 0.77)]);
                line(&[(-0.30, 0.77), (0.30, 0.77)]);
            }
            "panel-layers" => {
                // Three evenly spaced stacked diamond outlines.
                line(&[
                    (-0.82, -0.39), (0.0, -0.83),
                    (0.82, -0.39), (0.0, 0.06), (-0.82, -0.39),
                ]);
                line(&[(-0.82, -0.03), (0.0, 0.41), (0.82, -0.03)]);
                line(&[(-0.82, 0.32), (0.0, 0.76), (0.82, 0.32)]);
            }
            "wheel-undo" | "wheel-redo" => {
                // DeckCraft-inspired return arrows with a recognizable arrowhead.
                // Left-pointing Undo and mirrored right-pointing Redo share the
                // same consistent white stroke; no distorted cubic hooks.
                let direction = if icon == "wheel-undo" { 1.0 } else { -1.0 };
                let mut shaft = vec![
                    at(direction * -0.66, -0.20),
                    at(direction * 0.09, -0.20),
                ];
                // Smooth, clean quarter-circle turning into the return stem.
                for step in 1..=16 {
                    let angle = -PI / 2.0 + (step as f32 / 16.0) * PI / 2.0;
                    shaft.push(at(
                        direction * (0.09 + 0.44 * angle.cos()),
                        0.24 + 0.44 * angle.sin(),
                    ));
                }
                shaft.push(at(direction * 0.53, 0.47));
                p.add(Shape::line(shaft, stroke));
                line(&[
                    (direction * -0.31, -0.52),
                    (direction * -0.66, -0.20),
                    (direction * -0.31, 0.12),
                ]);
            }
            _ => {
                // Keep supported optional tools and hand exactly as upstream.
                designcraft_ui_egui::icons::paint(p, rect, icon, Color32::WHITE);
            }
        }
    }

    fn draw(&self, ui: &mut Ui, rectangle: Rect, selection: Option<usize>) {
        let radius = rectangle.width() / 2.0;
        let center = rectangle.center();
        // Paint beyond the plate's edge, but stay inside the padded Area.
        let p = ui.painter_at(rectangle.expand(20.0));
        // A short, feathered shadow. The low-alpha rings avoid the heavy
        // hard-edged blur reported in other ArtCraft wheel implementations.
        // PhotoCraft: compact 12-layer feathered shadow, softly offset down.
        for step in 0..12 {
            let spread = 12.0 - step as f32 * 0.82;
            let alpha = (2.0 + step as f32 * 0.42).round() as u8;
            p.circle_filled(center + vec2(0.8, 2.0), radius + spread,
                Color32::from_rgba_unmultiplied(0, 0, 0, alpha));
        }

        // PhotoCraft's alternating two-tone grey wheel plate, tinted only
        // on hovered slots. Keep a clearer A/B contrast in all eight sectors
        // while retaining the approved DesignCraft pink outer ring and hub.
        let dark_a = Color32::from_rgba_unmultiplied(41, 41, 44, self.alpha());
        let dark_b = Color32::from_rgba_unmultiplied(60, 60, 64, self.alpha());
        let pink = Color32::from_rgba_unmultiplied(160, 35, 68, self.alpha());
        // The previous painter submitted 12 separately antialiased quadrilaterals
        // PER SLOT, creating ~96 visible spokes. A single connected indexed
        // mesh uses shared edges and eliminates internal antialias seams.
        let mut plate = egui::epaint::Mesh::default();
        for i in 0..8 {
            let start = -PI / 2.0 - PI / 8.0 + i as f32 * TAU / 8.0;
            let finish = start + TAU / 8.0;
            let fill = if selection == Some(i) { pink }
                else if i % 2 == 0 { dark_a } else { dark_b };
            for step in 0..24 {
                let lo = start + (finish - start) * (step as f32 / 24.0);
                let hi = start + (finish - start) * ((step + 1) as f32 / 24.0);
                let at = |angle: f32, r: f32| center + vec2(angle.cos() * r, angle.sin() * r);
                let base = plate.vertices.len() as u32;
                plate.colored_vertex(at(lo, radius * 0.32), fill);
                plate.colored_vertex(at(lo, radius), fill);
                plate.colored_vertex(at(hi, radius), fill);
                plate.colored_vertex(at(hi, radius * 0.32), fill);
                plate.add_triangle(base, base + 1, base + 2);
                plate.add_triangle(base, base + 2, base + 3);
            }
        }
        p.add(Shape::mesh(plate));

        for i in 0..8 {
            let start = -PI / 2.0 - PI / 8.0 + i as f32 * TAU / 8.0;
            let finish = start + TAU / 8.0;
            let mark_angle = start + (finish - start) / 2.0;
            let mark = center + vec2(mark_angle.cos() * radius * 0.67, mark_angle.sin() * radius * 0.67);
            let icon = Rect::from_center_size(mark - vec2(0.0, 10.0), vec2(radius * 0.19, radius * 0.19));
            // Exact vector icon renderer from the upstream DesignCraft toolbar.
            Self::wheel_icon(&p, icon, ITEMS[self.slots[i]].1);
            p.text(mark + vec2(0.0, 17.0), Align2::CENTER_CENTER,
                ITEMS[self.slots[i]].0, FontId::proportional((radius * 0.088).max(10.0)), Color32::WHITE);
            let end = center + vec2(start.cos() * radius, start.sin() * radius);
            let inner = center + vec2(start.cos() * radius * 0.32, start.sin() * radius * 0.32);
            // Exactly eight faint boundaries, never the former 96 spokes.
            p.line_segment([inner, end], Stroke::new(0.75,
                Color32::from_rgba_unmultiplied(176, 176, 179, 88)));
        }
        // Image 1: a consistent thin pink circular rim in the exact Dc accent.
        // Thickness scales smoothly with the 75–125% wheel size slider.
        p.circle_stroke(center, radius - 1.5,
            Stroke::new((radius * 0.019).clamp(2.0, 3.3), ACCENT));
        p.circle_filled(center, radius * 0.32, BG);
        p.circle_stroke(center, radius * 0.32, Stroke::new(2.0, ACCENT));
        let logo = Self::original_dc_logo(ui.ctx());
        p.image(logo.id(),
            // 54% of Android.2's Dc mark (90% of Android.3); exact launcher artwork.
            Rect::from_center_size(center - vec2(0.0, radius * 0.052),
                vec2(radius * 0.4212, radius * 0.2646)),
            Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)),
            Color32::WHITE);
        let name = selection.map(|i| ITEMS[self.slots[i]].0).unwrap_or("DesignCraft");
        p.text(center + vec2(0.0, radius * 0.175), Align2::CENTER_CENTER,
            name, FontId::proportional(radius * 0.092), Color32::WHITE);
    }

    fn settings(&mut self, ctx: &Context) {
        if !self.settings_open { return; }
        self.open = false;
        let mut open = self.settings_open;
        let mut changed = false;
        // PhotoCraft reference: one compact panel, simple row-by-row assignments
        // and actual-scale preview OUTSIDE the customization window.
        let response = egui::Window::new("Stylus Wheel — Default")
            .id(Id::new("dc-wheel-customize-dialog"))
            .open(&mut open).resizable(false).collapsible(false)
            .frame(egui::Frame::window(ctx.style_of(egui::Theme::Dark).as_ref())
                .fill(Color32::from_rgb(48, 48, 50))
                .stroke(Stroke::new(0.8, Color32::from_rgb(76, 76, 80))))
            .default_width(336.0).show(ctx, |ui| {
                ui.label("Style: Default  •  8 segments");
                ui.label("Choose a tool for each position. Existing selections swap positions.");
                ui.add_space(4.0);
                ui.separator();
                ui.add_space(2.0);
                for i in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", i + 1));
                        ui.add_space(7.0);
                        let mut selected = self.slots[i];
                        egui::ComboBox::from_id_salt(("dc-wheel-slot", i))
                            .selected_text(ITEMS[selected].0).width(192.0)
                            .show_ui(ui, |ui| {
                                for n in 0..ITEMS.len() {
                                    ui.selectable_value(&mut selected, n, ITEMS[n].0);
                                }
                            });
                        if selected != self.slots[i] {
                            if let Some(previous) = self.slots.iter().position(|n| *n == selected) {
                                self.slots[previous] = self.slots[i];
                            }
                            self.slots[i] = selected;
                            changed = true;
                        }
                    });
                    ui.add_space(2.0);
                }
                ui.add_space(5.0);
                ui.separator();
                ui.add_space(3.0);
                ui.scope(|ui| {
                    // Dc accent applies only to wheel controls, not the app theme.
                    let visuals = &mut ui.style_mut().visuals;
                    visuals.selection.bg_fill = ACCENT;
                    visuals.widgets.active.bg_fill = ACCENT;
                    visuals.widgets.hovered.bg_fill = Color32::from_rgb(180, 45, 80);
                    ui.spacing_mut().slider_width = 160.0;
                    ui.horizontal(|ui| {
                        changed |= ui.add(egui::Slider::new(&mut self.size, 75.0..=125.0)
                            .suffix("%")).changed();
                        ui.label("Wheel size");
                    });
                    ui.horizontal(|ui| {
                        changed |= ui.add(egui::Slider::new(&mut self.opacity, 60.0..=100.0)
                            .suffix("%")).changed();
                        ui.label("Opacity");
                    });
                });
                ui.add_space(3.0);
                if ui.button("Restore Default").clicked() {
                    self.slots = DEFAULT;
                    self.size = 75.0;
                    self.opacity = 100.0;
                    changed = true;
                }
                ui.separator();
                ui.label("Actual-size preview appears beside this window.");
                ui.label("Size: 75–125%  •  Opacity: 60–100%");
                ui.label("Stylus button opens the wheel; hover never edits the canvas.");
            });
        self.settings_open = open;
        if changed { self.persist(); ctx.request_repaint(); }
        if self.settings_open {
            if let Some(result) = response {
                let screen = ctx.content_rect();
                let radius = self.radius();
                let diameter = radius * 2.0;
                let modal = result.response.rect;
                let x = if screen.right() - modal.right() >= diameter + 20.0 {
                    (modal.right() + screen.right()) / 2.0
                } else if modal.left() - screen.left() >= diameter + 20.0 {
                    (modal.left() + screen.left()) / 2.0
                } else { screen.center().x };
                let y = modal.center().y;
                // Reserve a 20pt margin around the actual-size wheel so
                // its new soft shadow is not clipped in the live preview.
                let margin = 20.0;
                let display = diameter + 2.0 * margin;
                let origin = pos2(
                    (x - radius - margin).clamp(screen.left(), (screen.right() - display).max(screen.left())),
                    (y - radius - margin).clamp(screen.top(), (screen.bottom() - display).max(screen.top())),
                );
                egui::Area::new(Id::new("dc-wheel-actual-size-preview"))
                    .order(Order::Foreground).fixed_pos(origin).interactable(false)
                    .show(ctx, |ui| {
                        let (rect, _) = ui.allocate_exact_size(vec2(display, display), Sense::hover());
                        self.draw(ui, rect.shrink(margin), None);
                    });
            }
        }
    }

    fn invoke(&mut self, app: &mut designcraft_ui_egui::DesignApp, slot: usize) {
        let item = self.slots[slot];
        let command = ITEMS[item].2;
        let result = match command {
            "window.panel" => app.run("window.panel", serde_json::json!({"panel": "layers"})).map(|_| ()),
            "edit.undo" | "edit.redo" => app.run(command, serde_json::json!({})).map(|_| ()),
            _ => {
                app.select_tool(command);
                Ok(())
            }
        };
        match result {
            Ok(()) => self.notify("Wheel selection accepted"),
            Err(error) => {
                app.status(format!("Stylus Wheel: {error}"));
                self.notify("Wheel command unavailable");
            }
        }
        self.open = false;
    }

    fn paint_live(&mut self, ctx: &Context, app: &mut designcraft_ui_egui::DesignApp) -> bool {
        if !self.open { return false; }
        let r = self.radius();
        self.clamp_center(ctx, self.center);
        let pointer = ctx.pointer_hover_pos();
        let selected = pointer.and_then(|pos| self.hit(pos));
        let in_circle = pointer.is_some_and(|p| (p - self.center).length() <= r);
        let margin = 20.0;
        let top_left = self.center - vec2(r + margin, r + margin);
        egui::Area::new(Id::new("dc-wheel-live"))
            .order(Order::Foreground).fixed_pos(top_left).interactable(true)
            .show(ctx, |ui| {
                let outer = 2.0 * (r + margin);
                let (rect, response) = ui.allocate_exact_size(vec2(outer, outer), Sense::click());
                self.draw(ui, rect.shrink(margin), selected);
                if response.clicked() {
                    if let Some(slot) = selected { self.invoke(app, slot); }
                    else {
                        self.open = false;
                        self.notify("Wheel cancelled");
                    }
                }
            });
        if ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.open = false;
            self.notify("Wheel cancelled");
        }
        ctx.request_repaint_after(Duration::from_millis(80));
        in_circle
    }
}

pub(super) fn blocks_hover(ctx: &Context) -> bool {
    ctx.data(|d| d.get_temp::<bool>(Id::new("dc-wheel-hover-block")).unwrap_or(false))
}

pub(super) fn ui(
    ui: &mut Ui,
    app: &mut designcraft_ui_egui::DesignApp,
    bridge: &super::saf::Bridge,
    actions: u16,
) {
    let ctx = ui.ctx().clone();
    let state_id = Id::new("dc-wheel-state");
    let mut wheel = ctx.data(|d| d.get_temp::<Wheel>(state_id)).unwrap_or_else(|| Wheel::load(&ctx));
    if actions & 64 != 0 {
        wheel.enabled = !wheel.enabled;
        wheel.last_device_scan = None;
        if !wheel.enabled { wheel.open = false; wheel.settings_open = false; }
        wheel.notify(if wheel.enabled {
            "Wheel ON • hover + single press"
        } else { "Wheel OFF" });
        wheel.persist();
    }
    if actions & 128 != 0 {
        wheel.settings_open = true;
        wheel.notify("Wheel settings • live preview");
    }
    let _ = bridge.dc_wheel_set_enabled(wheel.enabled);
    // Java sees only some MagicOS key events: the native AInputQueue captures
    // the pen rocker before winit and the invisible IME can consume it.
    if wheel.last_device_scan.is_none_or(|stamp| stamp.elapsed() >= Duration::from_secs(2)) {
        match bridge.dc_wheel_device_ids() {
            Ok(ids) => android_activity::dc_stylus_configure(wheel.enabled, &ids),
            Err(error) => {
                android_activity::dc_stylus_configure(false, &[]);
                log::warn!("DesignCraft wheel: device discovery failed: {error}");
            }
        }
        wheel.last_device_scan = Some(Instant::now());
    }
    let native_button = !android_activity::dc_stylus_native_take().is_empty();
    let java_button = bridge.dc_wheel_action().unwrap_or(0) != 0;
    if wheel.enabled && (native_button || java_button)
        && app.ui.dialog.is_none() && !app.session.wants_text()
        && !ctx.text_edit_focused() && !ctx.input(|i| i.pointer.any_down())
    {
        wheel.open = !wheel.open;
        if wheel.open {
            wheel.clamp_center(&ctx, ctx.pointer_hover_pos().unwrap_or(ctx.content_rect().center()));
            wheel.notify("Hover to highlight • tap tip to select");
        } else {
            wheel.notify("Wheel cancelled");
        }
    }
    wheel.settings(&ctx);
    let blocked = wheel.paint_live(&ctx, app);
    wheel.paint_feedback(&ctx);
    let enabled = wheel.enabled;
    ctx.data_mut(|d| {
        d.insert_temp(Id::new("dc-wheel-hover-block"), blocked);
        d.insert_temp(Id::new("dc-wheel-enabled"), enabled);
        d.insert_temp(state_id, wheel);
    });
    if enabled { ctx.request_repaint_after(Duration::from_millis(100)); }
}
