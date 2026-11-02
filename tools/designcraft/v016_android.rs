//! Android-only v0.16.0 font-import controls. Kept out of the upstream engine.
use super::{saf, saf_next_id, ImportRequest, SafState};
use std::sync::Mutex;

static RESULT: Mutex<Option<Result<String, String>>> = Mutex::new(None);

pub fn accept_font(name: &str, bytes: &[u8]) {
    let outcome = install_font(name, bytes);
    *RESULT.lock().unwrap_or_else(|e| e.into_inner()) = Some(outcome);
}

fn install_font(name: &str, bytes: &[u8]) -> Result<String, String> {
    use std::io::Write;
    let ext = std::path::Path::new(name).extension()
        .and_then(|s| s.to_str()).unwrap_or("").to_ascii_lowercase();
    if !matches!(ext.as_str(), "ttf" | "otf" | "ttc") || bytes.is_empty()
        || bytes.len() > 64 * 1024 * 1024
    {
        return Err("Choose a TTF/OTF/TTC font up to 64 MiB".into());
    }
    let header_ok = bytes.starts_with(&[0, 1, 0, 0])
        || bytes.starts_with(b"OTTO") || bytes.starts_with(b"ttcf");
    if !header_ok {
        return Err("Unsupported or damaged OpenType header".into());
    }
    let home = std::env::var_os("HOME").ok_or("Private font storage unavailable")?;
    let root = std::path::PathBuf::from(home).join(".local/share/fonts/imported");
    std::fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let filename: String = name.chars()
        .map(|c| if c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.') { c } else { '_' })
        .take(180).collect();
    if filename.is_empty() || filename.starts_with('.') {
        return Err("Invalid font filename".into());
    }
    let path = root.join(filename);
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true)
        .open(&path).map_err(|e| format!("Font already exists or cannot be written: {e}"))?;
    if let Err(e) = file.write_all(bytes).and_then(|_| file.sync_all()) {
        let _ = std::fs::remove_file(&path);
        return Err(e.to_string());
    }
    Ok(format!("Imported {} ({} bytes)", path.file_name().unwrap_or_default().to_string_lossy(), bytes.len()))
}

fn request_import(bridge: &saf::Bridge, state: &SafState) -> Result<(), String> {
    let id = saf_next_id(state);
    state.requests.lock().unwrap_or_else(|e| e.into_inner())
        .insert(id, ImportRequest { purpose: "android-font".into(), target: None });
    if let Err(e) = bridge.request_open(id, true) {
        state.requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
        return Err(e);
    }
    Ok(())
}

pub fn ui(
    ui: &mut egui::Ui,
    app: &mut designcraft_ui_egui::DesignApp,
    bridge: &saf::Bridge,
    state: &SafState,
) {
    if let Some(event) = RESULT.lock().unwrap_or_else(|e| e.into_inner()).take() {
        match event {
            Ok(message) => match app.run("font.reload", serde_json::json!({})) {
                Ok(_) => app.status(format!("{message}; font catalog refreshed")),
                Err(e) => app.status_error("Refresh imported fonts", e),
            },
            Err(e) => app.status_error("Import Font", e),
        }
    }
    if designcraft_ui_egui::menus::take_android_font_import() {
        if let Err(e) = request_import(bridge, state) {
            app.status_error("Import Font", e);
        }
    }
    // Visible even if the user hides the desktop File/Type menu bar.
    egui::TopBottomPanel::bottom("artcraft-designcraft-android-tools").show(ui.ctx(), |ui| {
        ui.horizontal(|ui| {
            ui.menu_button("Android", |ui| {
                if ui.button("Import Fonts (TTF/OTF/TTC)…").clicked() {
                    if let Err(e) = request_import(bridge, state) {
                        app.status_error("Import Font", e);
                    }
                    ui.close();
                }
                if ui.button("Refresh Fonts").clicked() {
                    if let Err(e) = app.run("font.reload", serde_json::json!({})) {
                        app.status_error("Refresh Fonts", e);
                    }
                    ui.close();
                }
                ui.separator();
                ui.label("D / C / S: unsaved-document dialog");
            });
        });
    });
}
