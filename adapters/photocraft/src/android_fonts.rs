//! Android SAF font import feedback and lazy file-backed font registration.
//! 5,000 cached paths / 4 GiB cumulative, 32 MiB each; never load whole library into RAM.
use crate::AndroidFileBridge;
use std::path::{Path, PathBuf};

pub(crate) struct AndroidFonts {
    message: Option<String>,
    visible: bool,
}
impl AndroidFonts {
    pub(crate) fn new(dir: &Path) -> Self {
        let mut fonts = Self { message: None, visible: false };
        if let Ok(files) = std::fs::read_dir(dir.join("PhotoCraft/fonts-imported")) {
            let paths: Vec<PathBuf> = files.flatten().map(|e| e.path()).take(5000).collect();
            let count = Self::register(&paths);
            if count > 0 { log::info!("Restored {count} imported font paths"); }
        }
        fonts
    }
    fn register(paths: &[PathBuf]) -> usize {
        if paths.is_empty() { return 0; }
        let Ok(mut shared) = photocraft_text::shared().lock() else {
            log::warn!("Could not lock shared PhotoCraft text font catalogue");
            return 0;
        };
        shared.fonts.register_font_paths(paths)
    }
    pub(crate) fn poll(&mut self, bridge: &AndroidFileBridge) {
        for _ in 0..4 {
            let value = match bridge.poll_font_import() {
                Ok(Some(s)) => s,
                Ok(None) => break,
                Err(err) => { self.message = Some(format!("Font picker: {err}")); self.visible = true; break; }
            };
            let Ok(info) = serde_json::from_str::<serde_json::Value>(&value) else { continue };
            let status = info["status"].as_str().unwrap_or("error");
            if status == "cancel" { continue; }
            if status != "ok" {
                self.message = Some(format!("Import Fonts: {}", info["message"].as_str().unwrap_or("Unknown Android error")));
                self.visible = true;
                continue;
            }
            let paths: Vec<PathBuf> = info["paths"].as_array().into_iter().flatten()
                .filter_map(|v| v.as_str().map(PathBuf::from)).take(5000).collect();
            let indexed = Self::register(&paths);
            let limit = if info["scan_limit_reached"].as_bool() == Some(true) { " (scan limit reached)" } else { "" };
            self.message = Some(format!("Imported fonts indexed: {indexed} / {} file(s){limit}. Refresh the font family dropdown.", paths.len()));
            self.visible = true;
        }
    }
    pub(crate) fn show(&mut self, ctx: &egui::Context) {
        if !self.visible { return; }
        let mut open = self.visible;
        egui::Window::new("Import Fonts")
            .open(&mut open)
            .collapsible(false)
            .resizable(false)
            .show(ctx, |ui| {
                if let Some(s) = &self.message { ui.label(s); }
                ui.label("Imported TTF/OTF fonts remain stored in PhotoCraft's private font folder.");
            });
        self.visible = open;
    }
}
