//! Android-only v0.16.0 font-import controls. Kept out of the upstream engine.
use super::{saf, saf_next_id, ImportRequest, SafState};
use std::sync::Mutex;

static RESULT: Mutex<Option<Result<String, String>>> = Mutex::new(None);

pub fn report_shared(event: Result<String, String>) {
    *RESULT.lock().unwrap_or_else(|error| error.into_inner()) = Some(event);
}

/// Handle physical keyboard input before egui text fields and modal widgets
/// consume it. NativeActivity also forwards hardware keys when its invisible
/// IME EditText owns Android focus.
pub fn handle_keys(
    app: &mut designcraft_ui_egui::DesignApp,
    ctx: &egui::Context,
    raw: &mut egui::RawInput,
    bridge: &saf::Bridge,
) {
    let dialog = app.ui.dialog.as_ref().is_some_and(|d| d.id == "closeDocument");
    if let Ok(action) = bridge.dc_dialog_action(dialog) {
        if (1..=3).contains(&action) {
            ctx.data_mut(|data| data.insert_temp(
                egui::Id::new("designcraft.unsaved.dcs"), action as u8
            ));
            ctx.request_repaint();
        }
    }
    let mut escape = false;
    let mut close = false;
    let mut tools = None;
    let mut modal_action = None;
    raw.events.retain_mut(|event| {
        if let egui::Event::Key {
            key, physical_key, pressed, repeat, modifiers, ..
        } = event {
            if *key == egui::Key::BrowserBack && !modifiers.any() {
                *key = egui::Key::Escape;
                *physical_key = Some(egui::Key::Escape);
            }
            if *pressed && !*repeat {
                if dialog && !modifiers.any() {
                    modal_action = match key {
                        egui::Key::D => Some(1),
                        egui::Key::C => Some(2),
                        egui::Key::S => Some(3),
                        _ => None,
                    };
                    if modal_action.is_some() { return false; }
                }
                if *key == egui::Key::Escape && !modifiers.any() {
                    escape = true;
                }
                if *key == egui::Key::W && (modifiers.ctrl || modifiers.command) {
                    close = true;
                    return false;
                }
                // Only use the Android fallback if the canvas is not editing.
                // Otherwise T and V are printable document text.
                if !dialog && app.ui.palette.is_none()
                    && !app.session.wants_text()
                    && !ctx.text_edit_focused()
                    && !modifiers.any()
                {
                    tools = match key {
                        egui::Key::T => Some("type"),
                        egui::Key::V => Some("selection"),
                        _ => None,
                    };
                    if tools.is_some() { return false; }
                }
            }
        }
        true
    });
    if let Some(action) = modal_action {
        ctx.data_mut(|data| data.insert_temp(
            egui::Id::new("designcraft.unsaved.dcs"), action
        ));
        raw.events.retain(|event| !matches!(event, egui::Event::Text(text)
            if matches!(text.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));
        ctx.request_repaint();
    }
    if escape && !dialog && app.ui.palette.is_none() && app.session.wants_text() {
        app.select_tool("selection");
        ctx.memory_mut(|memory| {
            if let Some(id) = memory.focused() { memory.surrender_focus(id); }
        });
    }
    if close && !dialog {
        if app.session.wants_text() { app.select_tool("selection"); }
        designcraft_ui_egui::menus::close_document(app, None);
        ctx.request_repaint();
    }
    if let Some(tool) = tools {
        app.select_tool(tool);
        raw.events.retain(|event| !matches!(event, egui::Event::Text(text)
            if (tool == "type" && text.eq_ignore_ascii_case("t"))
                || (tool == "selection" && text.eq_ignore_ascii_case("v"))));
        ctx.request_repaint();
    }
}

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

fn request_shared(bridge: &saf::Bridge, state: &SafState, refresh: bool)
    -> Result<(), String>
{
    bridge.dc_font_action(saf_next_id(state), refresh)
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
    let shared_actions = designcraft_ui_egui::menus::take_android_shared_actions();
    if shared_actions & 1 != 0 {
        if let Err(error) = request_shared(bridge, state, false) {
            app.status_error("Select Shared Font Folder", error);
        }
    }
    if shared_actions & 2 != 0 {
        if let Err(error) = request_shared(bridge, state, true) {
            app.status_error("Refresh Shared Fonts", error);
        }
    }
    if designcraft_ui_egui::menus::take_android_font_import() {
        if let Err(e) = request_import(bridge, state) {
            app.status_error("Import Font", e);
        }
    }
    // The Android menu is also in the main top-level menu bar. Keep a
    // prominent visible control for touch users who collapse the desktop bar.
    egui::Panel::top("artcraft-designcraft-android-tools").show(ui, |ui| {
        ui.horizontal(|ui| {
            ui.menu_button("Android Tools ▾", |ui| {
                if ui.button("Import Font (TTF/OTF/TTC)…").clicked() {
                    if let Err(e) = request_import(bridge, state) {
                        app.status_error("Import Font", e);
                    }
                    ui.close();
                }
                if ui.button("Select Shared Font Folder…").clicked() {
                    if let Err(e) = request_shared(bridge, state, false) {
                        app.status_error("Select Shared Font Folder", e);
                    }
                    ui.close();
                }
                if ui.button("Refresh Shared Fonts").clicked() {
                    if let Err(e) = request_shared(bridge, state, true) {
                        app.status_error("Refresh Shared Fonts", e);
                    }
                    ui.close();
                }
                if ui.button("Reload Font Catalog").clicked() {
                    if let Err(e) = app.run("font.reload", serde_json::json!({})) {
                        app.status_error("Reload Font Catalog", e);
                    }
                    ui.close();
                }
                ui.separator();
                ui.label("Ctrl+W → D / C / S; Esc exits typing; V/T tools");
            });
            ui.separator();
            ui.label("Shared Fonts • Keyboard");
        });
    });
}
