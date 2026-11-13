//! DesignCraft-specific Android stylus wheel. Isolated test candidate.
//! Reuses Storytold's toolbar icon painter; never modifies the document on hover.
use egui::{Align2, Color32, Context, FontId, Id, Order, Pos2, Rect, Sense, Shape, Stroke, Ui, pos2, vec2};
use std::{f32::consts::{PI, TAU}, fs, path::PathBuf, time::{Duration, Instant}};

const BG: Color32 = Color32::from_rgb(67, 8, 31);   // Owner supplied Dc icon: #43081F.
const ACCENT: Color32 = Color32::from_rgb(236, 72, 105); // #EC4869.
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
}

impl Wheel {
    fn load(ctx: &Context) -> Self {
        let path = std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".config/designcraft-stylus-wheel.v1"));
        let mut wheel = Self {
            enabled: false, settings_open: false, open: false,
            center: ctx.content_rect().center(), slots: DEFAULT,
            size: 100.0, opacity: 85.0, path, last_device_scan: None
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
        if icon == "wheel-shapes" {
            let c = rect.center();
            let d = rect.width() * 0.32;
            p.rect_stroke(Rect::from_center_size(c + vec2(-d * 0.58, -d * 0.7), vec2(d * 1.1, d * 1.1)),
                0.4, Stroke::new(1.8, Color32::WHITE), egui::StrokeKind::Middle);
            p.circle_stroke(c + vec2(d * 0.8, -d * 0.40), d * 0.54, Stroke::new(1.8, Color32::WHITE));
            let tip = c + vec2(0.0, d * 0.8);
            p.add(Shape::closed_line(vec![
                tip + vec2(0.0, -d*0.65), tip + vec2(-d*0.63, d*0.45),
                tip + vec2(d*0.63, d*0.45),
            ], Stroke::new(1.8, Color32::WHITE)));
        } else if icon == "wheel-undo" || icon == "wheel-redo" {
            // Familiar mirrored Undo / Redo: a clear left/right arrowhead
            // followed by a rounded return stroke (rather than a rotate glyph).
            let direction = if icon == "wheel-undo" { 1.0 } else { -1.0 };
            let scale = rect.width().min(rect.height());
            let at = |x: f32, y: f32| rect.center() + vec2(direction * x * scale, y * scale);
            let stroke = Stroke::new(2.2, Color32::WHITE);
            p.add(Shape::line(vec![
                at(-0.33, -0.11), at(-0.13, -0.11), at(0.04, -0.11),
                at(0.19, -0.05), at(0.29, 0.08), at(0.30, 0.20),
                at(0.23, 0.32), at(0.08, 0.37),
            ], stroke));
            p.add(Shape::line(vec![
                at(-0.11, -0.32), at(-0.33, -0.11), at(-0.11, 0.11),
            ], stroke));
        } else {
            // Use the same real icons as DesignCraft's own toolbar/panels.
            designcraft_ui_egui::icons::paint(p, rect, icon, Color32::WHITE);
        }
    }

    fn draw(&self, ui: &mut Ui, rectangle: Rect, selection: Option<usize>) {
        let radius = rectangle.width() / 2.0;
        let center = rectangle.center();
        // Paint beyond the plate's edge, but stay inside the padded Area.
        let p = ui.painter_at(rectangle.expand(20.0));
        // A short, feathered shadow. The low-alpha rings avoid the heavy
        // hard-edged blur reported in other ArtCraft wheel implementations.
        for step in (0..16).rev() {
            let fade = 1.0 - step as f32 / 16.0;
            let alpha = (10.0 * fade * fade).round() as u8;
            if alpha > 0 {
                p.circle_stroke(center + vec2(0.0, 3.0),
                    radius + 1.5 + step as f32 * 1.1,
                    Stroke::new(1.7, Color32::from_rgba_unmultiplied(0, 0, 0, alpha)));
            }
        }

        let dark = Color32::from_rgba_unmultiplied(51, 51, 54, self.alpha());
        let pink = Color32::from_rgba_unmultiplied(160, 35, 68, self.alpha());
        // The previous painter submitted 12 separately antialiased quadrilaterals
        // PER SLOT, creating ~96 visible spokes. A single connected indexed
        // mesh uses shared edges and eliminates internal antialias seams.
        let mut plate = egui::epaint::Mesh::default();
        for i in 0..8 {
            let start = -PI / 2.0 - PI / 8.0 + i as f32 * TAU / 8.0;
            let finish = start + TAU / 8.0;
            let fill = if selection == Some(i) { pink } else { dark };
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
        p.circle_stroke(center, radius - 1.0, Stroke::new(1.3, Color32::from_gray(120)));
        p.circle_filled(center, radius * 0.32, BG);
        p.circle_stroke(center, radius * 0.32, Stroke::new(2.0, ACCENT));
        let logo = Self::original_dc_logo(ui.ctx());
        p.image(logo.id(),
            // 60% of Android.2's Dc mark; preserve the exact launcher artwork.
            Rect::from_center_size(center - vec2(0.0, radius * 0.070),
                vec2(radius * 0.468, radius * 0.294)),
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
        let response = egui::Window::new("Stylus Wheel Customization")
            .id(Id::new("dc-wheel-customize-dialog"))
            .open(&mut open).resizable(false).collapsible(false)
            .default_width(360.0).show(ctx, |ui| {
                ui.label("DesignCraft · Default (8 customizable segments)");
                ui.label("Adjust tools, size and opacity. Preview uses the actual wheel scale.");
                ui.separator();
                changed |= ui.add(egui::Slider::new(&mut self.size, 75.0..=125.0).text("Wheel size").suffix("%")).changed();
                changed |= ui.add(egui::Slider::new(&mut self.opacity, 60.0..=100.0).text("Opacity").suffix("%")).changed();
                ui.separator();
                for i in 0..8 {
                    ui.horizontal(|ui| {
                        ui.label(format!("Slot {}", i + 1));
                        let mut selected = self.slots[i];
                        egui::ComboBox::from_id_salt(("dc-wheel-slot", i))
                            .selected_text(ITEMS[selected].0).width(185.0)
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
                }
                ui.separator();
                if ui.button("Restore Default").clicked() {
                    self.slots = DEFAULT;
                    self.size = 100.0;
                    self.opacity = 85.0;
                    changed = true;
                }
                ui.label("Hovering on the wheel never edits the canvas underneath.");
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
                let origin = pos2(
                    (x - radius).clamp(screen.left(), (screen.right() - diameter).max(screen.left())),
                    (y - radius).clamp(screen.top(), (screen.bottom() - diameter).max(screen.top())),
                );
                egui::Area::new(Id::new("dc-wheel-actual-size-preview"))
                    .order(Order::Foreground).fixed_pos(origin).interactable(false)
                    .show(ctx, |ui| {
                        let (rect, _) = ui.allocate_exact_size(vec2(diameter, diameter), Sense::hover());
                        self.draw(ui, rect, Some(1));
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
        if let Err(error) = result { app.status(format!("Stylus Wheel: {error}")); }
        self.open = false;
    }

    fn paint_live(&mut self, ctx: &Context, app: &mut designcraft_ui_egui::DesignApp) -> bool {
        if !self.open { return false; }
        let r = self.radius();
        self.clamp_center(ctx, self.center);
        let pointer = ctx.pointer_hover_pos();
        let selected = pointer.and_then(|pos| self.hit(pos));
        let in_circle = pointer.is_some_and(|p| (p - self.center).length() <= r);
        let top_left = self.center - vec2(r, r);
        egui::Area::new(Id::new("dc-wheel-live"))
            .order(Order::Foreground).fixed_pos(top_left).interactable(true)
            .show(ctx, |ui| {
                let (rect, response) = ui.allocate_exact_size(vec2(2.0 * r, 2.0 * r), Sense::click());
                self.draw(ui, rect, selected);
                if response.clicked() {
                    if let Some(slot) = selected { self.invoke(app, slot); }
                    else { self.open = false; }
                }
            });
        if ctx.input(|i| i.key_pressed(egui::Key::Escape)) {
            self.open = false;
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
        wheel.persist();
    }
    if actions & 128 != 0 { wheel.settings_open = true; }
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
        if wheel.open { wheel.clamp_center(&ctx, ctx.pointer_hover_pos().unwrap_or(ctx.content_rect().center())); }
    }
    wheel.settings(&ctx);
    let blocked = wheel.paint_live(&ctx, app);
    let enabled = wheel.enabled;
    ctx.data_mut(|d| {
        d.insert_temp(Id::new("dc-wheel-hover-block"), blocked);
        d.insert_temp(Id::new("dc-wheel-enabled"), enabled);
        d.insert_temp(state_id, wheel);
    });
    if enabled { ctx.request_repaint_after(Duration::from_millis(100)); }
}
