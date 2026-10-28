//! DesignCraft-specific Android controls using reviewed public command and font APIs.
use std::sync::{Mutex, OnceLock};
use super::{saf, SafState, saf_next_id, ImportRequest};

static GPU: OnceLock<String> = OnceLock::new();
static FONT_RESULT: Mutex<Option<Result<String, String>>> = Mutex::new(None);

pub fn record_gpu(cc: &eframe::CreationContext<'_>) {
    let text = match &cc.wgpu_render_state {
        Some(state) => {
            let info = state.adapter.get_info();
            format!("{} · {:?} · {:?}\nDriver: {} {}\nDocument rendering: CPU. Interface compositing: GPU.", info.name, info.backend, info.device_type, info.driver, info.driver_info)
        }
        None => "No wgpu adapter reported. Document rendering uses CPU.".to_owned(),
    };
    let _ = GPU.set(text);
}

pub fn font_result(result: Result<String, String>) {
    *FONT_RESULT.lock().unwrap_or_else(|e| e.into_inner()) = Some(result);
}

pub fn install_font(name: &str, bytes: &[u8]) -> Result<(), String> {
    use std::io::Write;
    let extension = std::path::Path::new(name).extension().and_then(|s| s.to_str()).unwrap_or("").to_ascii_lowercase();
    if !matches!(extension.as_str(), "ttf" | "otf") || bytes.len() > 32 * 1024 * 1024 {
        return Err("Choose a TTF or OTF file of at most 32 MB".into());
    }
    if !matches!(bytes.get(..4), Some([0, 1, 0, 0]) | Some([b'O', b'T', b'T', b'O'])) {
        return Err("The selected file has no supported OpenType header".into());
    }
    let home = std::env::var_os("HOME").ok_or("Private font directory is unavailable")?;
    let directory = std::path::PathBuf::from(home).join(".local/share/fonts/imported");
    std::fs::create_dir_all(&directory).map_err(|e| e.to_string())?;
    let safe_name: String = name.chars().map(|c| if c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '_') { c } else { '_' }).take(180).collect();
    let target = directory.join(safe_name);
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(&target)
        .map_err(|e| format!("Could not import font (existing names are preserved): {e}"))?;
    if let Err(error) = file.write_all(bytes).and_then(|_| file.sync_all()) {
        let _ = std::fs::remove_file(target);
        return Err(error.to_string());
    }
    Ok(())
}

pub struct Tablet {
    dock: bool,
    diagnostics: bool,
    toolbar_visible: bool,
    feedback: Option<(String, bool, f64)>,
}

fn toolbar_setting() -> Option<std::path::PathBuf> {
    std::env::var_os("HOME").map(|p|
        std::path::PathBuf::from(p).join(".local/share/designcraft/android-toolbar-visible"))
}

fn shortcut_setting() -> Option<std::path::PathBuf> {
    std::env::var_os("HOME").map(|p|
        std::path::PathBuf::from(p).join(".local/share/designcraft/android-shortcuts-enabled"))
}

impl Default for Tablet {
    fn default() -> Self {
        let dock = shortcut_setting().and_then(|p| std::fs::read(p).ok())
            .is_some_and(|value| value == b"enabled\n");
        let toolbar_visible = toolbar_setting().and_then(|p| std::fs::read(p).ok())
            .is_none_or(|value| value == b"shown\n");
        Self { dock, diagnostics: false, toolbar_visible, feedback: None }
    }
}

impl Tablet {
    fn set_toolbar_visible(&mut self, shown: bool) -> Result<(), String> {
        let path = toolbar_setting().ok_or("Toolbar preferences folder unavailable")?;
        let dir = path.parent().ok_or("Invalid toolbar preferences path")?;
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let pending = path.with_extension("tmp");
        std::fs::write(&pending, if shown { b"shown\n".as_slice() } else { b"hidden\n".as_slice() })
            .map_err(|e| e.to_string())?;
        std::fs::rename(pending, path).map_err(|e| e.to_string())?;
        self.toolbar_visible = shown;
        Ok(())
    }

    fn notify(&mut self, ui: &egui::Ui, message: String, error: bool) {
        self.feedback = Some((message, error, ui.input(|i| i.time) + 6.0));
        ui.ctx().request_repaint();
    }

    fn show_notification(&mut self, ui: &egui::Ui) {
        let Some((message, error, expires)) = &self.feedback else { return; };
        if ui.input(|i| i.time) >= *expires {
            self.feedback = None;
            return;
        }
        egui::Area::new(egui::Id::new("designcraft-font-import-notification"))
            .anchor(egui::Align2::RIGHT_TOP, egui::vec2(-18.0, 52.0))
            .order(egui::Order::Foreground)
            .show(ui.ctx(), |ui| {
                egui::Frame::popup(ui.style()).show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(if *error { "⚠" } else { "✓" });
                        ui.label(message.as_str());
                    });
                });
            });
        ui.ctx().request_repaint_after(std::time::Duration::from_millis(200));
    }

    fn save_shortcuts(&mut self, enabled: bool) -> Result<(), String> {
        let path = shortcut_setting().ok_or("App-private settings path is unavailable")?;
        let dir = path.parent().ok_or("Invalid app-private settings path")?;
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let pending = path.with_extension("tmp");
        std::fs::write(&pending, if enabled { b"enabled\n".as_slice() } else { b"disabled\n".as_slice() })
            .map_err(|e| e.to_string())?;
        std::fs::rename(pending, path).map_err(|e| e.to_string())?;
        self.dock = enabled;
        Ok(())
    }

    fn import_font(app: &mut designcraft_ui_egui::DesignApp, bridge: &saf::Bridge, state: &SafState) {
        let id = saf_next_id(state);
        state.requests.lock().unwrap_or_else(|e| e.into_inner())
            .insert(id, ImportRequest { purpose: "android-font".into(), target: None });
        if let Err(error) = bridge.request_open(id, true) {
            state.requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
            app.status_error("Import font", error);
        }
    }

    pub fn ui(&mut self, ui: &mut egui::Ui, app: &mut designcraft_ui_egui::DesignApp, bridge: &saf::Bridge, state: &SafState) {
        let font_event = FONT_RESULT.lock().unwrap_or_else(|e| e.into_inner()).take();
        if let Some(result) = font_event {
            match result {
                Ok(message) => match app.run("font.reload", serde_json::json!({})) {
                    Ok(_) => {
                        app.status(&format!("{message}; font catalog reloaded"));
                        self.notify(ui, format!("{message} — font list updated"), false);
                    }
                    Err(error) => {
                        app.status_error("Reload fonts", error.clone());
                        self.notify(ui, format!("Font import saved; reload failed: {error}"), true);
                    }
                },
                Err(error) => {
                    app.status_error("Import font", error.clone());
                    self.notify(ui, format!("Font import failed: {error}"), true);
                }
            }
        }
        // Queued by the reviewed Android-only Type, Window and Help commands.
        let actions = designcraft_ui_egui::menus::artcraft_take_android_actions();
        if actions & 1 != 0 { Self::import_font(app, bridge, state); }
        for (mask, label, code) in [
            (2, "Select shared font folder", 1), (4, "Refresh shared fonts", 2),
            (8, "Check for updates", 3), (16, "Update settings", 4)
        ] {
            if actions & mask != 0 {
                if let Err(error) = bridge.tablet_action(code) { app.status_error(label, error); }
            }
        }
        if actions & 32 != 0 {
            if let Err(error) = self.save_shortcuts(!self.dock) {
                app.status_error("Touch shortcuts", error);
            }
        }
        if actions & 64 != 0 {
            if let Err(error) = self.set_toolbar_visible(!self.toolbar_visible) {
                app.status_error("Android toolbar", error);
            }
        }
        if self.toolbar_visible {
        egui::Panel::bottom("designcraft-android-controls").show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.menu_button("Android", |ui| {
                    if ui.button("Import TTF / OTF…").clicked() {
                        Self::import_font(app, bridge, state);
                    }
                    if ui.button("Reload fonts").clicked() {
                        if let Err(error) = app.run("font.reload", serde_json::json!({})) { app.status_error("Reload fonts", error); }
                    }
                    for (label, action) in [("Select shared font folder…", 1), ("Refresh shared fonts", 2), ("Check for updates", 3), ("Startup update settings…", 4)] {
                        if ui.button(label).clicked() {
                            if let Err(error) = bridge.tablet_action(action) { app.status_error(label, error); }
                        }
                    }
                    ui.label("Shared fonts are cached locally; refresh adds or updates files. Startup network checks default to off.");
                    if ui.checkbox(&mut self.dock, "Touch shortcuts").changed() {
                        let enabled = self.dock;
                        if let Err(error) = self.save_shortcuts(enabled) {
                            self.dock = !enabled;
                            app.status_error("Touch shortcuts", error);
                        }
                    }
                    ui.checkbox(&mut self.diagnostics, "GPU diagnostics");
                    ui.label("Customize keys: Edit → Keyboard Shortcuts");
                });
                if self.dock {
                    egui::ScrollArea::horizontal().id_salt("designcraft-android-shortcut-scroll").show(ui, |ui| {
                        ui.horizontal(|ui| {
                            for (label, command) in [
                                ("Undo", "edit.undo"), ("Redo", "edit.redo"), ("Save", "file.save")
                            ] {
                                let enabled = !ui.ctx().text_edit_focused();
                                if ui.add_enabled(enabled,
                                    egui::Button::new(label).min_size(egui::vec2(56.0, 44.0))).clicked()
                                {
                                    if let Err(error) = app.run(command, serde_json::json!({})) {
                                        app.status_error(label, error);
                                    }
                                }
                            }
                        });
                    });
                }
            });
        });
        }
        self.show_notification(ui);
        if self.diagnostics {
            egui::Window::new("Android graphics diagnostics").open(&mut self.diagnostics).show(ui.ctx(), |ui| {
                ui.label(GPU.get().map(String::as_str).unwrap_or("Adapter details unavailable"));
                ui.label("Vulkan / GLES selection comes from the Android builder. A working graphics driver is still required for the interface.");
            });
        }
    }
}
