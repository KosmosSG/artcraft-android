//! ArtCraft NativeActivity-compatible shortcut pad (initial test integration).
//! Inspired by morte2437/photocraft-android Shortcut Pad, MIT/Apache-2.0.
//! This does not copy the fork's GameActivity-specific input router.
use photocraft_ui_egui::{menus, PhotocraftApp};
use serde_json::json;
use std::path::PathBuf;

pub(crate) struct ShortcutPad {
    reserved: Option<egui::Rect>,
    visible_file: PathBuf,
    left_file: PathBuf,
    last_visible: bool,
    last_left: bool,
    zoom_angle: Option<f32>,
    zoom_turn: f32,
    held_alt: bool,
    held_pan: bool,
    last_alt: bool,
    last_pan: bool,
}
impl ShortcutPad {
    pub(crate) fn new(data_dir: PathBuf) -> Self {
        let visible_file = data_dir.join("shortcut-pad-visible");
        let left_file = data_dir.join("shortcut-pad-left");
        let visible = visible_file.is_file();
        let left = left_file.is_file();
        menus::artcraft_pad_set_visible(visible);
        menus::artcraft_pad_set_left(left);
        Self { reserved: None, visible_file, left_file, last_visible: visible, last_left: left,
            zoom_angle: None, zoom_turn: 0.0,
            held_alt: false, held_pan: false,
            last_alt: false, last_pan: false }
    }
    /// Inject only transitions (press/release), never endless key repeats.
    /// Holding Pan sends Space, like PhotoCraft's normal temporary Hand tool.
    /// Holding Alt delivers the native AltLeft modifier to the current tool.
    pub(crate) fn inject_controls(&mut self, raw: &mut egui::RawInput) {
        for (held, old, key) in [
            (self.held_alt, &mut self.last_alt, egui::Key::AltLeft),
            (self.held_pan, &mut self.last_pan, egui::Key::Space),
        ] {
            if held == *old { continue; }
            *old = held;
            raw.events.push(egui::Event::Key {
                key, physical_key: None, pressed: held, repeat: false,
                modifiers: egui::Modifiers {
                    alt: self.held_alt,
                    ..egui::Modifiers::NONE
                },
            });
        }
    }
    fn save_flag(path: &PathBuf, value: bool) {
        if value {
            if let Some(parent) = path.parent() {
                if let Err(e) = std::fs::create_dir_all(parent) { log::warn!("Shortcut Pad settings directory: {e}"); return; }
            }
            if let Err(e) = std::fs::write(path, b"1") { log::warn!("Shortcut Pad setting: {e}"); }
        } else if let Err(e) = std::fs::remove_file(path) {
            if e.kind() != std::io::ErrorKind::NotFound { log::warn!("Shortcut Pad setting removal: {e}"); }
        }
    }
    fn action(app: &mut PhotocraftApp, ctx: &egui::Context, id: &str) {
        if let Err(e) = menus::invoke(app, ctx, id, json!({})) {
            log::warn!("Shortcut Pad command {id}: {e}");
        }
        ctx.request_repaint();
    }
    // Reference Pad::reserve requires a fork-specific PhotocraftApp.edge_strip
    // that is NOT present in upstream v0.19. Keep our official upstream pinned:
    // Use egui 0.37's Panel API, laid out inside the upstream root Ui.
    pub(crate) fn reserve(&mut self, ui: &mut egui::Ui) {
        self.reserved = None;
        if !menus::artcraft_pad_visible() { return; }
        let panel = if menus::artcraft_pad_left() {
            egui::Panel::left("artcraft_pad_reserved_left")
        } else {
            egui::Panel::right("artcraft_pad_reserved_right")
        };
        panel.exact_size(78.0).show(ui, |panel_ui| {
            self.reserved = Some(panel_ui.max_rect());
        });
    }
    pub(crate) fn show(&mut self, ctx: &egui::Context, app: &mut PhotocraftApp) {
        let show = menus::artcraft_pad_visible();
        let left = menus::artcraft_pad_left();
        if show {
            // Keep a narrow, untitled edge dock like the reference tablet port.
            // This is a NativeActivity-compatible Area, not a floating settings
            // dialog. Full GameActivity touch capture/pen wheel is a later phase.
            // Reference fork uses app.edge_strip and edge_strip_rect,
            // NOT a floating panel over the Properties sidebar.
            // Only draw in the rect the upstream engine reserved.
            let Some(strip) = self.reserved else { return };
            egui::Area::new(egui::Id::new("artcraft_android_edge_pad"))
                .order(egui::Order::Foreground)
                .fixed_pos(strip.min)
                .movable(false)
                .show(ctx, |ui| {
                    let frame = egui::Frame::new()
                        .fill(egui::Color32::from_rgb(54, 56, 62))
                        .corner_radius(0.0)
                        .inner_margin(egui::Margin::same(3));
                    frame.show(ui, |ui| {
                        ui.set_min_size(egui::vec2(strip.width() - 6.0, strip.height() - 6.0));
                        ui.vertical_centered(|ui| {
                            if ui.add_sized([66.0, 46.0], egui::Button::new("Undo")).clicked() {
                                Self::action(app, ctx, "edit.undo");
                            }
                            if ui.add_sized([66.0, 46.0], egui::Button::new("Redo")).clicked() {
                                Self::action(app, ctx, "edit.redo");
                            }
                            ui.add_space(7.0);
                            let (ring, gesture) = ui.allocate_exact_size(
                                egui::vec2(68.0, 68.0), egui::Sense::click_and_drag());
                            let center = ring.center();
                            ui.painter().circle_filled(center, 33.0, egui::Color32::from_gray(63));
                            ui.painter().circle_stroke(center, 29.0,
                                egui::Stroke::new(2.0, egui::Color32::from_gray(140)));
                            ui.painter().circle_stroke(center, 23.0,
                                egui::Stroke::new(1.0, egui::Color32::from_gray(95)));
                            ui.painter().text(center, egui::Align2::CENTER_CENTER, "Zoom",
                                egui::FontId::proportional(11.0), egui::Color32::WHITE);
                            if gesture.clicked() {
                                // Tapping the upper/lower ring acts as + / -.
                                let plus = gesture.interact_pointer_pos()
                                    .is_some_and(|pos| pos.y < center.y);
                                Self::action(app, ctx, if plus { "view.zoomIn" } else { "view.zoomOut" });
                            }
                            if gesture.dragged() {
                                // The reference Shortcut Pad uses a *rotary* wheel:
                                // clockwise zooms in, counter-clockwise zooms out.
                                if let Some(pos) = gesture.interact_pointer_pos() {
                                    let v = pos - center;
                                    let angle = v.y.atan2(v.x);
                                    if let Some(previous) = self.zoom_angle {
                                        let turn = (angle - previous + std::f32::consts::PI)
                                            .rem_euclid(std::f32::consts::TAU)
                                            - std::f32::consts::PI;
                                        self.zoom_turn += turn;
                                        if self.zoom_turn.abs() >= 0.38 {
                                            Self::action(app, ctx, if self.zoom_turn > 0.0 {
                                                "view.zoomIn"
                                            } else {
                                                "view.zoomOut"
                                            });
                                            self.zoom_turn = 0.0;
                                        }
                                    }
                                    self.zoom_angle = Some(angle);
                                }
                            } else {
                                self.zoom_angle = None;
                                self.zoom_turn = 0.0;
                            }
                            ui.add_space(7.0);
                            let alt = ui.add_sized([66.0, 43.0],
                                egui::Button::new("Alt"));
                            self.held_alt = alt.is_pointer_button_down_on();
                            let pan = ui.add_sized([66.0, 43.0],
                                egui::Button::new("Pan"));
                            self.held_pan = pan.is_pointer_button_down_on();
                            if self.held_alt || self.held_pan { ctx.request_repaint(); }
                            // Bottom keys stay inside the reserved sidebar, not a
                            // floating Area over the document's Properties panel.
                            let used = ui.cursor().min.y - strip.top();
                            ui.add_space((strip.height() - used - 100.0).max(4.0));
                            if ui.add_sized([66.0, 36.0],
                                egui::Button::new("⛶ Screen")).clicked() {
                                Self::action(app, ctx, "view.screenMode.cycle");
                            }
                            if ui.add_sized([66.0, 36.0],
                                egui::Button::new("⌨ Keys")).clicked() {
                                menus::artcraft_queue_pc_menu_action(17);
                            }
                            // Hide/Show remains under Window → Shortcut Pad; no
                            // extra buttons should widen the reference-style strip.
                        });
                    });
                });
        }
        let now = menus::artcraft_pad_visible();
        if now != self.last_visible {
            Self::save_flag(&self.visible_file, now);
            self.last_visible = now;
        }
        if left != self.last_left {
            Self::save_flag(&self.left_file, left);
            self.last_left = left;
        }
    }
}
