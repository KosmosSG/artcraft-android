//! ArtCraft NativeActivity-compatible shortcut pad (initial test integration).
//! Inspired by morte2437/photocraft-android Shortcut Pad, MIT/Apache-2.0.
//! This does not copy the fork's GameActivity-specific input router.
use photocraft_ui_egui::{menus, PhotocraftApp};
use serde_json::json;
use std::path::PathBuf;

pub(crate) struct ShortcutPad {
    visible_file: PathBuf,
    left_file: PathBuf,
    last_visible: bool,
    last_left: bool,
    zoom_drag_y: f32,
}
impl ShortcutPad {
    pub(crate) fn new(data_dir: PathBuf) -> Self {
        let visible_file = data_dir.join("shortcut-pad-visible");
        let left_file = data_dir.join("shortcut-pad-left");
        let visible = visible_file.is_file();
        let left = left_file.is_file();
        menus::artcraft_pad_set_visible(visible);
        menus::artcraft_pad_set_left(left);
        Self { visible_file, left_file, last_visible: visible, last_left: left, zoom_drag_y: 0.0 }
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
    pub(crate) fn show(&mut self, ctx: &egui::Context, app: &mut PhotocraftApp) {
        let show = menus::artcraft_pad_visible();
        let left = menus::artcraft_pad_left();
        if show {
            // Keep a narrow, untitled edge dock like the reference tablet port.
            // This is a NativeActivity-compatible Area, not a floating settings
            // dialog. Full GameActivity touch capture/pen wheel is a later phase.
            let anchor = if left { egui::Align2::LEFT_CENTER } else { egui::Align2::RIGHT_CENTER };
            let offset = if left { [3.0, 0.0] } else { [-3.0, 0.0] };
            egui::Area::new(egui::Id::new("artcraft_android_edge_pad"))
                .order(egui::Order::Foreground)
                .anchor(anchor, offset)
                .movable(false)
                .show(ctx, |ui| {
                    let frame = egui::Frame::new()
                        .fill(egui::Color32::from_rgb(54, 56, 62))
                        .corner_radius(10.0)
                        .inner_margin(6.0);
                    frame.show(ui, |ui| {
                        ui.set_width(72.0);
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
                                // A slow vertical swipe runs one zoom step at a
                                // time, rather than repeatedly on every frame.
                                let total = gesture.drag_delta().y;
                                let difference = total - self.zoom_drag_y;
                                if difference.abs() >= 24.0 {
                                    Self::action(app, ctx, if difference < 0.0 {
                                        "view.zoomIn"
                                    } else {
                                        "view.zoomOut"
                                    });
                                    self.zoom_drag_y = total;
                                }
                            } else {
                                self.zoom_drag_y = 0.0;
                            }
                            ui.add_space(7.0);
                            // These two controls are intentionally unavailable
                            // until held-modifier and pan JNI are device-tested.
                            ui.add_enabled(false, egui::Button::new("Alt"))
                                .on_disabled_hover_text("Held modifier integration pending");
                            ui.add_enabled(false, egui::Button::new("Pan"))
                                .on_disabled_hover_text("Pan integration pending");
                            ui.separator();
                            if ui.add_sized([66.0, 34.0], egui::Button::new("V  Move")).clicked() {
                                Self::action(app, ctx, "tools.select.move");
                            }
                            if ui.add_sized([66.0, 34.0], egui::Button::new("B Brush")).clicked() {
                                Self::action(app, ctx, "tools.select.brush");
                            }
                            if ui.add_sized([66.0, 34.0], egui::Button::new("T  Type")).clicked() {
                                Self::action(app, ctx, "tools.select.type");
                            }
                            ui.separator();
                            // Never interfere with Android system keyboard/IME
                            // until the existing IME bridge is fully validated.
                            if ui.small_button("Hide Pad").clicked() {
                                menus::artcraft_pad_set_visible(false);
                            }
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
