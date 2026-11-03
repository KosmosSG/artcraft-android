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
}
impl ShortcutPad {
    pub(crate) fn new(data_dir: PathBuf) -> Self {
        let visible_file = data_dir.join("shortcut-pad-visible");
        let left_file = data_dir.join("shortcut-pad-left");
        let visible = visible_file.is_file();
        let left = left_file.is_file();
        menus::artcraft_pad_set_visible(visible);
        menus::artcraft_pad_set_left(left);
        Self { visible_file, left_file, last_visible: visible, last_left: left }
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
        let mut show = menus::artcraft_pad_visible();
        let left = menus::artcraft_pad_left();
        if show {
            let anchor = if left { egui::Align2::LEFT_CENTER } else { egui::Align2::RIGHT_CENTER };
            let offset = if left { [9.0, 0.0] } else { [-9.0, 0.0] };
            egui::Window::new("Shortcut Pad")
                .id(egui::Id::unique("artcraft_android_shortcut_pad"))
                .anchor(anchor, offset)
                .collapsible(false)
                .resizable(false)
                .open(&mut show)
                .show(ctx, |ui| {
                    ui.set_min_width(88.0);
                    if ui.button("↶ Undo").clicked() { Self::action(app, ctx, "edit.undo"); }
                    if ui.button("↷ Redo").clicked() { Self::action(app, ctx, "edit.redo"); }
                    ui.separator();
                    ui.label("Zoom wheel");
                    ui.horizontal(|ui| {
                        if ui.button("−").clicked() { Self::action(app, ctx, "view.zoomOut"); }
                        if ui.button("+").clicked() { Self::action(app, ctx, "view.zoomIn"); }
                    });
                    ui.separator();
                    if ui.button("V  Move").clicked() { Self::action(app, ctx, "tools.select.move"); }
                    if ui.button("B  Brush").clicked() { Self::action(app, ctx, "tools.select.brush"); }
                    if ui.button("T  Type").clicked() { Self::action(app, ctx, "tools.select.type"); }
                    ui.separator();
                    ui.small("Window → Shortcut Pad");
                });
        }
        if show != menus::artcraft_pad_visible() { menus::artcraft_pad_set_visible(show); }
        if show != self.last_visible {
            Self::save_flag(&self.visible_file, show);
            self.last_visible = show;
        }
        if left != self.last_left {
            Self::save_flag(&self.left_file, left);
            self.last_left = left;
        }
    }
}
