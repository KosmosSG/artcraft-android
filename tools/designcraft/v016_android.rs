//! Android-only v0.16.0 font-import controls. Kept out of the upstream engine.
use super::{saf, saf_next_id, ImportRequest, SafState};
use std::sync::{Mutex, atomic::{AtomicBool, Ordering}};

static SHOW_ANDROID_TOOLS: AtomicBool = AtomicBool::new(true);
static SHARED_SCAN_PENDING: AtomicBool = AtomicBool::new(false);
static USER_MESSAGE: Mutex<String> = Mutex::new(String::new());
static GPU_STATUS: Mutex<String> = Mutex::new(String::new());

pub fn set_gpu_adapter(message: String) {
    *GPU_STATUS.lock().unwrap_or_else(|e| e.into_inner()) = message;
}

fn feedback(message: impl Into<String>) {
    *USER_MESSAGE.lock().unwrap_or_else(|e| e.into_inner()) = message.into();
}


static RESULT: Mutex<Option<Result<String, String>>> = Mutex::new(None);

pub fn report_shared(event: Result<String, String>) {
    SHARED_SCAN_PENDING.store(false, Ordering::Relaxed);
    *RESULT.lock().unwrap_or_else(|error| error.into_inner()) = Some(event);
}

pub fn show_android_tools() -> bool {
    SHOW_ANDROID_TOOLS.load(Ordering::Relaxed)
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
    // The native Activity sees physical T/V even when winit/IME drops the
    // associated egui Key event. Consume it only outside document typing.
    let android_tool = if !dialog && app.ui.dialog.is_none()
        && app.ui.palette.is_none() && !app.session.wants_text()
        && !ctx.text_edit_focused()
    {
        match bridge.dc_tool_action() {
            Ok(1) => Some("type"),
            Ok(2) => Some("selection"),
            Ok(3) => Some("hand"),
            Ok(4) => Some("zoom"),
            Ok(5) => Some("directSelection"),
            Ok(6) => Some("pen"),
            Ok(7) => Some("pencil"),
            Ok(8) => Some("rectangleFrame"),
            Ok(9) => Some("rectangle"),
            Ok(10) => Some("contentCollector"),
            _ => None,
        }
    } else {
        // Discard queued T/V if the app entered editing or another modal.
        let _ = bridge.dc_tool_action();
        None
    };
    // Native Activity queues physical Esc/Ctrl+W even when a stale IME host
    // swallows the original KeyEvent. RawInput may contain the same event;
    // boolean coalescing guarantees each action runs at most once per frame.
    let mut escape = bridge.dc_escape_action().is_ok_and(|value| value != 0);
    let command = bridge.dc_close_action().unwrap_or(0);
    let mut close = command == 1;
    let mut quit = command == 2;
    let mut tools = android_tool;
    let mut modal_action: Option<u8> = None;
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
                if *key == egui::Key::Q && (modifiers.ctrl || modifiers.command) && !modifiers.shift && !modifiers.alt {
                    quit = true;
                    return false;
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
                        egui::Key::H => Some("hand"),
                        egui::Key::Z => Some("zoom"),
                        egui::Key::A => Some("directSelection"),
                        egui::Key::P => Some("pen"),
                        egui::Key::N => Some("pencil"),
                        egui::Key::F => Some("rectangleFrame"),
                        egui::Key::M => Some("rectangle"),
                        egui::Key::B => Some("contentCollector"),
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
    if escape && !dialog && app.ui.palette.is_none() {
        if app.session.wants_text() {
            // Committing the edit explicitly fixes the stale text caret left
            // behind when Android's invisible IME consumes the first Esc.
            // Preserve the text, then switch back to Selection.
            let _ = app.run("text.exitToFrame", serde_json::json!({}));
            app.select_tool("selection");
        }
        // A stale focused egui EditText previously blocked T/V indefinitely
        // even after the document editor had exited.
        ctx.memory_mut(|memory| {
            if let Some(id) = memory.focused() { memory.surrender_focus(id); }
        });
        ctx.request_repaint();
    }
    if quit && app.ui.dialog.is_none() {
        if app.session.wants_text() {
            let _ = app.run("text.exitToFrame", serde_json::json!({}));
        }
        app.request_quit();
        ctx.request_repaint();
    } else if close && app.ui.dialog.is_none() {
        if app.session.wants_text() { let _ = app.run("text.exitToFrame", serde_json::json!({})); }
        designcraft_ui_egui::menus::close_document(app, None);
        ctx.request_repaint();
    }
    if let Some(tool) = tools {
        app.select_tool(tool);
        // A physical tool key may ALSO arrive as an egui Text event. Remove
        // exactly its matching printable character to avoid adding a stray
        // glyph when switching tools; never touch arbitrary document text.
        let shortcut = match tool {
            "type" => "t", "selection" => "v", "hand" => "h",
            "zoom" => "z", "directSelection" => "a", "pen" => "p",
            "pencil" => "n", "rectangleFrame" => "f",
            "rectangle" => "m", "contentCollector" => "b", _ => "",
        };
        raw.events.retain(|event| !matches!(event, egui::Event::Text(text)
            if !shortcut.is_empty() && text.eq_ignore_ascii_case(shortcut)));
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
    if SHARED_SCAN_PENDING.swap(true, Ordering::Relaxed) {
        feedback("A shared-font scan is already running…");
        return Ok(());
    }
    feedback(if refresh {
        "Refreshing shared fonts… Scan includes subfolders."
    } else {
        "Select your shared font folder in the Android picker…"
    });
    match bridge.dc_font_action(saf_next_id(state), refresh) {
        Ok(()) => Ok(()),
        Err(error) => {
            SHARED_SCAN_PENDING.store(false, Ordering::Relaxed);
            feedback(format!("Shared fonts: {error}"));
            Err(error)
        }
    }
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

/// Fallback when the Android IME or embedded winit path delivers a text
/// event but not the physical Key event. Never consume printable characters
/// inside an active text editor. Raw-input and JNI handling remain primary.
fn forward_ui_shortcuts(ui: &mut egui::Ui, app: &mut designcraft_ui_egui::DesignApp) {
    let ctx = ui.ctx();
    let unsaved = app.ui.dialog.as_ref().is_some_and(|d| d.id == "closeDocument");
    if unsaved {
        let choice = ui.input(|input| {
            if input.modifiers.any() { return None; }
            input.events.iter().find_map(|event| match event {
                egui::Event::Key { key, pressed: true, repeat: false, .. } =>
                    match key {
                        egui::Key::D => Some(1_u8),
                        egui::Key::C => Some(2_u8),
                        egui::Key::S => Some(3_u8),
                        _ => None,
                    },
                egui::Event::Text(value) =>
                    match value.as_str() {
                        "d" | "D" => Some(1),
                        "c" | "C" => Some(2),
                        "s" | "S" => Some(3),
                        _ => None,
                    },
                _ => None,
            })
        });
        if let Some(choice) = choice {
            ctx.data_mut(|data| data.insert_temp(
                egui::Id::new("designcraft.unsaved.dcs"), choice
            ));
            ctx.request_repaint();
        }
        return;
    }
    if app.ui.dialog.is_some() || app.ui.palette.is_some()
        || app.session.wants_text() || ctx.text_edit_focused()
    {
        return;
    }
    let tool = ui.input(|input| {
        if input.modifiers.any() { return None; }
        input.events.iter().find_map(|event| {
            // Some Android IMEs commit one printable hardware key as Text
            // instead of Key; preserve ordinary typing and every UI editor.
            let letter = match event {
                egui::Event::Key { key, pressed: true, repeat: false, modifiers, .. }
                    if !modifiers.any() =>
                    match key {
                        egui::Key::T => Some('t'), egui::Key::V => Some('v'),
                        egui::Key::H => Some('h'), egui::Key::Z => Some('z'),
                        egui::Key::A => Some('a'), egui::Key::P => Some('p'),
                        egui::Key::N => Some('n'), egui::Key::F => Some('f'),
                        egui::Key::M => Some('m'), egui::Key::B => Some('b'),
                        _ => None,
                    },
                egui::Event::Text(text) if text.chars().count() == 1 =>
                    text.chars().next().map(|ch| ch.to_ascii_lowercase()),
                _ => None,
            };
            match letter {
                Some('t') => Some("type"),
                Some('v') => Some("selection"),
                Some('h') => Some("hand"),
                Some('z') => Some("zoom"),
                Some('a') => Some("directSelection"),
                Some('p') => Some("pen"),
                Some('n') => Some("pencil"),
                Some('f') => Some("rectangleFrame"),
                Some('m') => Some("rectangle"),
                Some('b') => Some("contentCollector"),
                _ => None,
            }
        })
    });
    if let Some(tool) = tool {
        app.select_tool(tool);
        ctx.request_repaint();
    }
}

/// Visible tool feedback beside the hotspot on systems that override native pointer icons.
pub fn paint_pointer_feedback(ctx: &egui::Context) {
    use egui::CursorIcon as C;
    if !egui_winit::winit::platform::android::HARDWARE_POINTER.load(Ordering::Relaxed) {
        return;
    }
    let Some(pos) = ctx.pointer_hover_pos() else { return };
    // Draw paths rather than font symbols, so custom font catalogs cannot
    // substitute a missing glyph for the cursor.
    let hand: &[(i8, i8)] = &[(-4,1),(-2,2),(-2,-4),(0,-5),(1,-1),(4,-1),(5,2),(3,5),(-1,5),(-4,1)];
    let paths: &[&[(i8, i8)]] = match ctx.output(|o| o.cursor_icon) {
        C::Text | C::VerticalText => &[&[(-3,-5),(3,-5)], &[(0,-5),(0,5)], &[(-3,5),(3,5)]],
        C::Grab | C::Grabbing | C::PointingHand => &[hand],
        C::Move | C::AllScroll => &[&[(-5,0),(5,0)], &[(0,-5),(0,5)], &[(-5,0),(-3,-2)], &[(5,0),(3,2)]],
        C::Crosshair | C::Cell | C::ZoomIn => &[&[(-5,0),(5,0)], &[(0,-5),(0,5)]],
        C::ZoomOut => &[&[(-5,0),(5,0)]],
        C::ResizeHorizontal | C::ResizeColumn | C::ResizeEast | C::ResizeWest =>
            &[&[(-3,-2),(-5,0),(-3,2)], &[(-5,0),(5,0)], &[(3,-2),(5,0),(3,2)]],
        C::ResizeVertical | C::ResizeRow | C::ResizeNorth | C::ResizeSouth =>
            &[&[(-2,-3),(0,-5),(2,-3)], &[(0,-5),(0,5)], &[(-2,3),(0,5),(2,3)]],
        C::ResizeNwSe | C::ResizeNorthWest | C::ResizeSouthEast =>
            &[&[(-4,0),(-4,-4),(0,-4)], &[(-4,-4),(4,4)], &[(0,4),(4,4),(4,0)]],
        C::ResizeNeSw | C::ResizeNorthEast | C::ResizeSouthWest =>
            &[&[(0,-4),(4,-4),(4,0)], &[(-4,4),(4,-4)], &[(-4,0),(-4,4),(0,4)]],
        _ => return,
    };
    let painter = ctx.layer_painter(egui::LayerId::new(egui::Order::Tooltip,
        egui::Id::unique("designcraft.tool-pointer")));
    let center = pos + egui::vec2(13.0, 17.0);
    let stroke = egui::Stroke::new(1.3, egui::Color32::WHITE);
    painter.circle_filled(center, 8.5, egui::Color32::from_gray(35));
    painter.circle_stroke(center, 8.5, stroke);
    for path in paths {
        for edge in path.windows(2) {
            let point = |(x, y): (i8, i8)| center + egui::vec2(f32::from(x), f32::from(y));
            painter.line_segment([point(edge[0]), point(edge[1])], stroke);
        }
    }
}

pub fn ui(
    ui: &mut egui::Ui,
    app: &mut designcraft_ui_egui::DesignApp,
    bridge: &saf::Bridge,
    state: &SafState,
) {
    forward_ui_shortcuts(ui, app);
    if app.ui.dialog.as_ref().is_some_and(|d| d.id == "closeDocument") {
        // The native Activity queues D/C/S separately. A repaint tick keeps
        // the egui raw-input hook polling JNI even when those key events were
        // consumed by a focused Android IME EditText.
        ui.ctx().request_repaint_after(std::time::Duration::from_millis(80));
    }
    if let Some(event) = RESULT.lock().unwrap_or_else(|e| e.into_inner()).take() {
        match event {
            Ok(message) => match app.run("font.reload", serde_json::json!({})) {
                Ok(_) => {
                    feedback(format!("{message}; font catalog refreshed"));
                    app.status(format!("{message}; font catalog refreshed"));
                },
                Err(e) => {
                    feedback(format!("Font catalog refresh failed: {e}"));
                    app.status_error("Refresh fonts", e);
                },
            },
            Err(e) => {
                feedback(format!("Shared fonts: {e}"));
                app.status_error("Shared fonts", e);
            },
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
    // Android is a permanent top-level menu even when this compact toolbar
    // is hidden. Keep processing scan results while the toolbar is invisible.
    if designcraft_ui_egui::menus::take_android_tools_toggle() {
        SHOW_ANDROID_TOOLS.fetch_xor(true, Ordering::Relaxed);
        ui.ctx().request_repaint();
    }
    if SHARED_SCAN_PENDING.load(Ordering::Relaxed) {
        // SAF scanning happens asynchronously; continue polling and repainting.
        ui.ctx().request_repaint_after(std::time::Duration::from_millis(300));
    }
    // The approved Dc menu now lives INSIDE the upstream menu bar, beside Home.
    // Consume actions selected in that UI, preserving the Android bridge and
    // all existing SAF font, updater and diagnostic behavior without a top strip.
    let dc_actions = designcraft_ui_egui::menus::take_dc_menu_actions();
    if dc_actions & 1 != 0 {
        if let Err(error) = request_import(bridge, state) {
            app.status_error("Import Fonts", error);
        }
    }
    if dc_actions & 2 != 0 {
        if let Err(error) = request_shared(bridge, state, false) {
            app.status_error("Select Shared Font Folder", error);
        }
    }
    if dc_actions & 4 != 0 {
        if let Err(error) = request_shared(bridge, state, true) {
            app.status_error("Refresh Shared Fonts", error);
        }
    }
    if dc_actions & 8 != 0 {
        if let Err(error) = app.run("font.reload", serde_json::json!({})) {
            app.status_error("Reload Font Catalog", error);
        }
    }
    if dc_actions & 16 != 0 {
        if let Err(error) = bridge.dc_update_action(3) {
            app.status_error("Check Updates", error);
        }
    }
    if dc_actions & 32 != 0 {
        if let Err(error) = bridge.dc_update_action(4) {
            app.status_error("Startup Update Check", error);
        }
    }
}
