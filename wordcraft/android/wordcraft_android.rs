//! WordCraft-only Android UI and JNI extensions.
//! No signing, APK downloading, silent installs or broad storage permissions.
use android_activity::AndroidApp;
use eframe::egui;
use jni::{JavaVM, jni_sig, strings::JNIString, objects::{JObject, JString, JValue}};
use serde_json::Value;
use std::collections::VecDeque;
use std::cell::{Cell, RefCell};
use std::sync::Arc;
use std::time::{Duration, Instant};
mod refresh_feedback;
use refresh_feedback::FontRefresh;

const ACTIONS: [(&str, &str); 9] = [
    ("Undo", "edit.undo"),
    ("Redo", "edit.redo"),
    ("Save", "file.save"),
    ("Bold", "format.bold"),
    ("Italic", "format.italic"),
    ("Zoom in", "view.zoomIn"),
    ("Zoom out", "view.zoomOut"),
    ("Select all", "select.all"),
    ("Print", "file.print"),
];

pub struct Tools {
    app: AndroidApp,
    vm: Arc<JavaVM>,
    show_pad: bool,
    startup_updates: bool,
    status: String,
    release_url: Option<String>,
    update_checking: bool,
    update_manual: bool,
    update_visible: bool,
    update_message: String,
    update_started: Option<Instant>,
    pending_fonts: VecDeque<String>,
    fonts: FontRefresh,
    slots: [usize; 6],
    paste_key_held: Cell<bool>,
    recent_paste: RefCell<Option<(Instant, String)>>,
}

impl Tools {
    /// Normalize WordCraft Android clipboard delivery before WordApp processes
    /// input. GameActivity, egui-winit and the hidden MagicOS IME can emit the
    /// SAME copied characters as Paste and Text/Commit in separate frames.
    ///
    /// Do not require an egui Key::V keydown: winit sometimes consumes that
    /// key while synthesizing its own Paste. Preserve one system clipboard
    /// event per explicit Ctrl+V press or ribbon paste, while filtering short
    /// delayed echoes of the same data. No clipboard contents are logged.
    pub fn deduplicate_clipboard_input(&self, raw: &mut egui::RawInput) {
        let was_held = self.paste_key_held.get();
        let paste_down = raw.events.iter().any(|event| matches!(
            event,
            egui::Event::Key {
                key: egui::Key::V, pressed: true, repeat: false, modifiers, ..
            } if (modifiers.ctrl || modifiers.command) && !modifiers.alt && !modifiers.shift
        ));
        let paste_repeat = raw.events.iter().any(|event| matches!(
            event,
            egui::Event::Key {
                key: egui::Key::V, pressed: true, repeat: true, modifiers, ..
            } if (modifiers.ctrl || modifiers.command) && !modifiers.alt && !modifiers.shift
        ));
        let paste_up = raw.events.iter().any(|event| matches!(
            event, egui::Event::Key { key: egui::Key::V, pressed: false, .. }
        ));
        let lost_focus = raw.events.iter().any(|event| matches!(
            event, egui::Event::WindowFocused(false)
        ));
        // An independent new Key down following a release is allowed even if
        // it pastes the same character quickly. A held/repeated key is not.
        let fresh_press = paste_down && !was_held;
        let held_repeat = paste_repeat || (paste_down && was_held);
        let now = Instant::now();
        let recent = self.recent_paste.borrow().as_ref().and_then(|(at, text)| {
            (now.duration_since(*at) <= Duration::from_millis(110))
                .then(|| text.clone())
        });
        let keep_last = raw.events.iter().rposition(|event| matches!(
            event, egui::Event::Paste(_)
        ));
        let current = keep_last.and_then(|index| match &raw.events[index] {
            egui::Event::Paste(text) => Some(text.clone()),
            _ => None,
        });
        // Upstream WordCraft maps Ctrl+V itself to edit.paste (see
        // storyteller/wordcraft engine cmd/edit.rs). The Android launcher
        // ALSO synthesizes an egui Paste from this very same Ctrl+V. Sending
        // both through WordApp pastes A twice, even with just one Paste event.
        // Prefer the explicit Android clipboard Paste; consume only the
        // matching command keydown and preserve key-up, Copy/Cut and text.
        let has_clipboard_paste = current.is_some();
        // A Paste can arrive without a matching Key event. Compare only the
        // exact payload; unrelated IME commits and normal text are preserved.
        let echo_text = current.as_deref().or(recent.as_deref());
        let mut index = 0usize;
        let mut paste_in = 0usize;
        let mut paste_out = 0usize;
        let mut echo_dropped = 0usize;
        let mut duplicate_key_dropped = 0usize;
        raw.events.retain(|event| {
            let at = index;
            index += 1;
            match event {
                egui::Event::Key {
                    key: egui::Key::V, pressed: true, modifiers, ..
                } if (modifiers.ctrl || modifiers.command)
                    && !modifiers.alt && !modifiers.shift
                    && (has_clipboard_paste || held_repeat) => {
                    // If we let this keydown reach WordApp it calls edit.paste
                    // independently of the explicit egui::Event::Paste below.
                    duplicate_key_dropped += 1;
                    false
                }
                egui::Event::Paste(text) => {
                    paste_in += 1;
                    let is_recent_echo = !fresh_press
                        && recent.as_deref() == Some(text.as_str());
                    let keep = !held_repeat && Some(at) == keep_last
                        && !is_recent_echo;
                    if keep { paste_out += 1; } else { echo_dropped += 1; }
                    keep
                }
                egui::Event::Text(text)
                | egui::Event::Ime(egui::ImeEvent::Commit(text))
                    if echo_text == Some(text.as_str())
                        && (current.is_some() || recent.is_some()) => {
                    echo_dropped += 1;
                    false
                }
                _ => true,
            }
        });
        if paste_out > 0 {
            if let Some(text) = current {
                *self.recent_paste.borrow_mut() = Some((now, text));
            }
        }
        if paste_down { self.paste_key_held.set(true); }
        if paste_up || lost_focus { self.paste_key_held.set(false); }
        if lost_focus { self.recent_paste.borrow_mut().take(); }
        if paste_in > 0 || echo_dropped > 0 || duplicate_key_dropped > 0
            || paste_down || paste_repeat {
            log::info!(
                "WC_PASTE_DIAG paste_in={} paste_out={} echo_dropped={} key_suppressed={} new_key={} held_repeat={}",
                paste_in, paste_out, echo_dropped, duplicate_key_dropped,
                fresh_press, held_repeat
            );
        }
    }

    /// Capture D/C/S while the save-changes prompt is active, at eframe's raw
    /// input hook *before* the editor, focus navigation or popup can consume it.
    /// The Android Activity bridge is an independent fallback for physical keys
    /// that never appear in egui's input stream (GameActivity/IME routing).

    /// Convert Java ACTION_SCROLL on the MagicPad trackpad into egui's native
    /// precise scroll event, preserving the WordCraft upstream 1:1 canvas path.
    /// Touchscreen gesture events and buttons pass through unchanged.
    pub fn inject_trackpad_scroll(
        &self,
        ctx: &egui::Context,
        raw: &mut egui::RawInput,
        modifiers: egui::Modifiers,
    ) {
        let Ok(Some(sample)) = self.call_string("wcTakeTrackpadScroll") else {
            return;
        };
        let mut values = sample.split(',');
        let parse = |value: Option<&str>| value.and_then(|s| s.parse::<f32>().ok());
        let (Some(dx), Some(dy), Some(x), Some(y)) = (
            parse(values.next()), parse(values.next()),
            parse(values.next()), parse(values.next()),
        ) else {
            return;
        };
        if values.next().is_some() || ![dx, dy, x, y].iter().all(|n| n.is_finite()) {
            return;
        }
        let scale = ctx.pixels_per_point();
        if !scale.is_finite() || scale <= 0.0 || (dx == 0.0 && dy == 0.0) {
            return;
        }
        // Android MotionEvent positions are in device pixels. Advancing the
        // cursor before the wheel makes WordCraft scroll the hovered canvas,
        // even if Android never emitted a winit CursorMoved for this trackpad.
        raw.events.push(egui::Event::PointerMoved(egui::pos2(x / scale, y / scale)));
        raw.events.push(egui::Event::MouseWheel {
            unit: egui::MouseWheelUnit::Point,
            delta: egui::vec2(dx / scale, dy / scale),
            phase: egui::TouchPhase::Move,
            source: egui::MouseWheelSource::Trackpad,
            modifiers,
        });
        ctx.request_repaint();
    }

    /// WC_ANDROID_STYLUS_SAMPLES_V1: bring native MotionEvent history/hover
    /// into egui, retaining all sampled points until upstream ink.rs consumes
    /// this frame's bounded batch. This does not change normal touch events.
    pub fn inject_stylus_motion(&self, ctx: &egui::Context) {
        let scale = ctx.pixels_per_point();
        if !scale.is_finite() || scale <= 0.0 { return; }
        let samples = self.call_string("wcTakeStylusTrail").ok().flatten()
            .map(|text| text.split(';').take(256).filter_map(|sample| {
                let (x, y) = sample.split_once(',')?;
                let (Ok(x), Ok(y)) = (x.parse::<f32>(), y.parse::<f32>()) else {
                    return None;
                };
                (x.is_finite() && y.is_finite()).then_some([x / scale, y / scale])
            }).collect::<Vec<[f32; 2]>>())
            .unwrap_or_default();
        let hover = self.call_string("wcStylusHoverPosition").ok().flatten()
            .and_then(|sample| {
                let (x, y) = sample.split_once(',')?;
                let (Ok(x), Ok(y)) = (x.parse::<f32>(), y.parse::<f32>()) else {
                    return None;
                };
                (x.is_finite() && y.is_finite()).then_some([x / scale, y / scale])
            });
        let got_samples = !samples.is_empty();
        ctx.data_mut(|d| {
            if got_samples {
                d.insert_temp(egui::Id::new("wc_stylus.path_samples"), samples);
            } else {
                d.remove::<Vec<[f32; 2]>>(egui::Id::new("wc_stylus.path_samples"));
            }
            if let Some(pos) = hover {
                d.insert_temp(egui::Id::new("wc_stylus.hover_pos"), pos);
            } else {
                d.remove::<[f32; 2]>(egui::Id::new("wc_stylus.hover_pos"));
            }
        });
        if got_samples { ctx.request_repaint(); }
        if hover.is_some() { ctx.request_repaint_after(Duration::from_millis(32)); }
    }

    /// MagicOS may report hardware letters as Key, Text or IME Commit.
    /// Intercept only unmodified D/C/S while Save Changes is showing;
    /// Ctrl+Shift+S is a separate nonmodal Save As shortcut.

    // Translate stable two-finger touchscreen movement to precise canvas pan.
    // Preserve native touch/pinch input, so zoom and selection still work.
    pub fn inject_touch_pan(&self, ctx: &egui::Context, raw: &mut egui::RawInput, modifiers: egui::Modifiers) {
        let Ok(Some(sample)) = self.call_string("wcTakeTwoFingerPan") else { return };
        let parts: Vec<_> = sample.split(',').collect();
        if parts.len() != 4 { return; }
        let Ok(values) = parts.iter().map(|v| v.parse::<f32>()).collect::<Result<Vec<_>, _>>() else { return };
        let scale = ctx.pixels_per_point();
        if !scale.is_finite() || scale <= 0.0 || !values.iter().all(|n| n.is_finite()) { return; }
        let (dx, dy, x, y) = (values[0], values[1], values[2], values[3]);
        if dx == 0.0 && dy == 0.0 { return; }
        raw.events.push(egui::Event::PointerMoved(egui::pos2(x / scale, y / scale)));
        raw.events.push(egui::Event::MouseWheel {
            unit: egui::MouseWheelUnit::Point,
            delta: egui::vec2(dx / scale, dy / scale),
            phase: egui::TouchPhase::Move,
            source: egui::MouseWheelSource::Trackpad,
            modifiers,
        });
        ctx.request_repaint();
    }

    pub fn capture_unsaved_keys(&self, active: bool, ctx: &egui::Context, raw: &mut egui::RawInput) {
        let id = egui::Id::new("wordcraft.unsaved.dcs");
        if !active {
            ctx.data_mut(|d| d.remove::<u8>(id));
        }
        // RawInput has no modifiers field in egui 0.37. Prefer the latest
        // modifier-bearing event from this frame; use the previous egui state
        // only for input methods that deliver committed text with no Key event.
        let text_modifiers = raw.events.iter().rev().find_map(|event| match event {
            egui::Event::Key { modifiers, .. } => Some(*modifiers),
            egui::Event::ModifiersChanged(modifiers) => Some(*modifiers),
            _ => None,
        }).unwrap_or_else(|| ctx.input(|input| input.modifiers));
        let allow_text_choice = active && !text_modifiers.any();
        let mut choice = None;
        let mut save_as = false;
        let mut quit = false;
        raw.events.retain(|event| match event {
            egui::Event::Key { key, physical_key, pressed, repeat, modifiers, .. } => {
                let actual_key = (*physical_key).unwrap_or(*key);
                if active && actual_key == egui::Key::Escape && !modifiers.any() {
                    if *pressed && !*repeat && choice.is_none() { choice = Some(2); }
                    return false; // Esc means Cancel, never Don't Save.
                }
                if !active && actual_key == egui::Key::Q
                    && modifiers.ctrl && !modifiers.shift
                    && !modifiers.alt && !modifiers.mac_cmd
                {
                    if *pressed && !*repeat { quit = true; }
                    return false;
                }
                if !active && actual_key == egui::Key::S
                    && modifiers.ctrl && modifiers.shift
                    && !modifiers.alt && !modifiers.mac_cmd
                {
                    if *pressed && !*repeat { save_as = true; }
                    return false; // Consume down and up without modifying document text.
                }
                if active && !modifiers.any() {
                    let action = match actual_key {
                        egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0,
                    };
                    if action != 0 {
                        if *pressed && !*repeat && choice.is_none() { choice = Some(action); }
                        return false;
                    }
                }
                true
            }
            egui::Event::Text(text) if allow_text_choice => {
                let action = match text.as_str() {
                    "d" | "D" => 1, "c" | "C" => 2, "s" | "S" => 3, _ => 0,
                };
                if action == 0 { return true; }
                if choice.is_none() { choice = Some(action); }
                false
            }
            egui::Event::Ime(egui::ImeEvent::Commit(text)) if allow_text_choice => {
                let action = match text.as_str() {
                    "d" | "D" => 1, "c" | "C" => 2, "s" | "S" => 3, _ => 0,
                };
                if action == 0 { return true; }
                if choice.is_none() { choice = Some(action); }
                false
            }
            egui::Event::Text(text) if active && choice.is_some()
                && matches!(text.as_str(), "d" | "D" | "c" | "C" | "s" | "S") => false,
            _ => true,
        });
        if let Some(action) = choice {
            log::info!("WC_DCS_DIAG raw_choice={action}");
            ctx.data_mut(|d| {
                if d.get_temp::<u8>(id).is_none() { d.insert_temp(id, action); }
            });
            ctx.request_repaint();
        }
        if quit {
            log::info!("WC_SHORTCUT_DIAG raw_ctrl_q");
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("wordcraft.shortcut.quit"), true));
            ctx.request_repaint();
        }
        if save_as {
            log::info!("WC_SHORTCUT_DIAG raw_ctrl_shift_s");
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("wordcraft.shortcut.save_as"), true));
            ctx.request_repaint();
        }
    }
    pub fn unsaved_dialog(&self, active: bool, ctx: &egui::Context) {
        if !active { ctx.data_mut(|d| d.remove::<u8>(egui::Id::new("wordcraft.unsaved.dcs"))); }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let result = vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, JNIString::new("wcUnsavedDialog"), jni_sig!("(Z)I"), &[JValue::Bool(active.into())]);
            if result.is_err() { env.exception_clear(); }
            result?.i()
        });
        if let Ok(action @ 1..=3) = result {
            if active { ctx.data_mut(|d| { let id = egui::Id::new("wordcraft.unsaved.dcs"); if d.get_temp::<u8>(id).is_none() { d.insert_temp(id, action as u8); } }); }
        }
        if active { ctx.request_repaint_after(std::time::Duration::from_millis(16)); }
    }
    pub fn new(app: &AndroidApp) -> Self {
        // SAFETY: AndroidApp owns the JavaVM for the Activity's lifetime.
        let vm = Arc::new(unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) });
        let mut tools = Self {
            app: app.clone(), vm, show_pad: false,
            startup_updates: false, status: "Ready".to_owned(),
            release_url: None, update_checking: false, update_manual: false,
            update_visible: false, update_message: String::new(),
            update_started: None, pending_fonts: VecDeque::new(),
            fonts: FontRefresh::default(), slots: [0, 1, 2, 3, 4, 5],
            paste_key_held: Cell::new(false),
            recent_paste: RefCell::new(None),
        };
        tools.startup_updates = tools.call_bool("wcStartupUpdates").unwrap_or(false);
        if let Ok(Some(saved)) = tools.call_string("wcGetShortcutPad") {
            for (i, id) in saved.split(',').take(6).enumerate() {
                if let Some(index) = ACTIONS.iter().position(|(_, command)| *command == id) {
                    tools.slots[i] = index;
                }
            }
        }
        // The unified verified updater owns startup checks. Keep the legacy
        // read-only methods for compatibility, but never trigger a second check here.
        if tools.call_bool("wcHasFontFolder").unwrap_or(false) {
            tools.status = tools.fonts.start();
            if let Err(error) = tools.call_void("wcRefreshFontFolder") {
                tools.status = tools.fonts.stop(format!("Font refresh error: {error}"));
            }
        }
        tools
    }

    fn call_void(&self, method: &'static str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            // SAFETY: AndroidApp retains the global Activity reference.
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, JNIString::new(method), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn call_bool(&self, method: &'static str) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, JNIString::new(method), jni_sig!("()Z"), &[])?.z()
        }).map_err(|error| error.to_string())
    }

    fn call_string(&self, method: &'static str) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(
                &*activity, JNIString::new(method), jni_sig!("()Ljava/lang/String;"), &[],
            )?.l()?;
            if value.is_null() { return Ok(None); }
            let value = JString::cast_local(env, value)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|error| error.to_string())
    }

    fn call_bool_arg(&self, method: &'static str, value: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(
                &*activity, JNIString::new(method), jni_sig!("(Z)V"),
                &[JValue::Bool(value)],
            )?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn call_string_arg(&self, method: &'static str, value: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let string = JObject::from(env.new_string(value)?);
            env.call_method(
                &*activity, JNIString::new(method), jni_sig!("(Ljava/lang/String;)V"),
                &[JValue::Object(&string)],
            )?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn save_pad(&mut self) {
        let choices = self.slots.iter()
            .map(|i| ACTIONS[*i].1).collect::<Vec<_>>().join(",");
        if let Err(error) = self.call_string_arg("wcSetShortcutPad", &choices) {
            self.status = format!("Could not save shortcut choices: {error}");
        }
    }

    pub fn poll(&mut self, app: &mut wordcraft_ui_egui::WordApp, ctx: &egui::Context) {
        // WC_ANDROID_FAST_INPUT_V1: soft keyboard commits live in Java's queue.
        // GameActivity need not wake Rust on each IME commit, so keep frames
        // responsive while editing without polling continuously while idle.
        if self.call_bool("wcFastInputActive").unwrap_or(false) {
            ctx.request_repaint_after(Duration::from_millis(16));
        }
        let raw_quit = ctx.data_mut(|d|
            d.remove_temp::<bool>(egui::Id::new("wordcraft.shortcut.quit"))
        ).unwrap_or(false);
        let java_quit = self.call_bool("wcTakeQuit").unwrap_or(false);
        if raw_quit || java_quit {
            // Upstream quit() checks for unsaved data and opens D/C/S when needed.
            if app.quit() { ctx.send_viewport_cmd(egui::ViewportCommand::Close); }
            ctx.request_repaint();
        }
        // Drain both native and Activity fallbacks; one dialog if both saw a key.
        let raw_save_as = ctx.data_mut(|d|
            d.remove_temp::<bool>(egui::Id::new("wordcraft.shortcut.save_as"))
        ).unwrap_or(false);
        let java_save_as = self.call_bool("wcTakeSaveAs").unwrap_or(false);
        if raw_save_as || java_save_as {
            if app.has_document() {
                app.save_as_dialog(); // Preserve upstream Android SAF Save As flow.
                self.status = "Save As opened (Ctrl+Shift+S)".to_owned();
            } else {
                self.status = "Open or create a document before Save As".to_owned();
                app.status(self.status.clone());
            }
            ctx.request_repaint();
        }
        if self.call_bool("wcTakeNewDocument").unwrap_or(false) {
            match app.run("file.new", serde_json::json!({})) {
                Ok(_) => self.status = "New document requested".into(),
                Err(error) => self.status = format!("New document: {error}"),
            }
            ctx.request_repaint();
        }
        for _ in 0..2 {
            match self.call_string("wcPollFontResult") {
                Ok(Some(raw)) => {
                    match serde_json::from_str::<Value>(&raw) {
                        Ok(result) => match result["state"].as_str().unwrap_or("") {
                            "ok" => {
                                self.pending_fonts.clear();
                                if let Some(paths) = result["paths"].as_array() {
                                    for path in paths.iter().filter_map(Value::as_str) {
                                        self.pending_fonts.push_back(path.to_owned());
                                    }
                                }
                                self.status = self.fonts.staged(
                                    self.pending_fonts.len(),
                                    result["skipped"].as_u64().unwrap_or(0) as usize,
                                    result["limited"].as_bool().unwrap_or(false),
                                );
                            }
                            "cancelled" => {
                                self.pending_fonts.clear();
                                self.status = self.fonts.stop("Font folder selection cancelled".into());
                            }
                            _ => {
                                self.pending_fonts.clear();
                                self.status = self.fonts.stop(result["message"].as_str()
                                    .unwrap_or("Shared font folder could not be read").to_owned());
                            }
                        },
                        Err(_) => {
                            self.pending_fonts.clear();
                            self.status = self.fonts.stop("Could not read the font refresh result".into());
                        }
                    }
                    app.status(self.status.clone());
                    ctx.request_repaint();
                }
                Ok(None) => break,
                Err(error) => {
                    self.pending_fonts.clear();
                    self.status = self.fonts.stop(format!("Font folder bridge error: {error}"));
                    app.status(self.status.clone());
                    ctx.request_repaint();
                    break;
                }
            }
        }
        for _ in 0..8 {
            let Some(path) = self.pending_fonts.pop_front() else { break };
            let success = match app.run("font.add", serde_json::json!({"path": path})) {
                Ok(_) => true,
                Err(error) => {
                    log::info!("WordCraft shared font already available or rejected: {error}");
                    false
                }
            };
            self.status = self.fonts.record(success);
            app.status(self.status.clone());
            ctx.request_repaint();
        }
        // Background SAF work cannot wake an idle egui frame by itself. Poll
        // while refreshing so completion appears without another tap.
        if self.fonts.busy {
            ctx.request_repaint_after(Duration::from_millis(100));
        }
        match self.call_string("wcPollUpdateResult") {
            Ok(Some(raw)) => {
                let manual = self.update_manual;
                self.update_checking = false;
                self.update_manual = false;
                self.update_started = None;
                self.release_url = None;
                match serde_json::from_str::<Value>(&raw) {
                    Ok(result) => {
                        let state = result["state"].as_str().unwrap_or("error");
                        match state {
                            "update_available" => {
                                let latest = result["latest"].as_str().unwrap_or("unknown");
                                self.release_url = result["url"].as_str().map(str::to_owned);
                                self.status = format!("WordCraft Android update available: {latest}");
                            }
                            "up_to_date" => self.status = "WordCraft Android is up to date".into(),
                            "no_release" => self.status = "No published WordCraft Android APK release yet".into(),
                            _ => self.status = result["message"].as_str()
                                .unwrap_or("Could not check WordCraft Android releases").to_owned(),
                        }
                        // Quiet startup checks except when a newer signed release is available.
                        if manual || state == "update_available" {
                            self.update_visible = true;
                        }
                    }
                    Err(_) => {
                        self.status = "Could not read WordCraft update response".into();
                        if manual { self.update_visible = true; }
                    }
                }
                self.update_message = self.status.clone();
                if manual {
                    let _ = self.call_string_arg("wcShowUpdateMessage", &self.status);
                }
                app.status(self.status.clone());
                ctx.request_repaint();
            }
            Ok(None) => {}
            Err(error) => {
                self.update_checking = false;
                self.update_started = None;
                self.status = format!("Update-check bridge error: {error}");
                self.update_message = self.status.clone();
                if self.update_manual {
                    self.update_visible = true;
                    let _ = self.call_string_arg("wcShowUpdateMessage", &self.status);
                }
                self.update_manual = false;
                app.status(self.status.clone());
                ctx.request_repaint();
            }
        }
        if self.update_checking {
            if self.update_started.is_some_and(|started| started.elapsed() > Duration::from_secs(30)) {
                self.update_checking = false;
                self.update_started = None;
                self.status = "WordCraft update check timed out. Check your connection and try again.".into();
                self.update_message = self.status.clone();
                if self.update_manual {
                    self.update_visible = true;
                    let _ = self.call_string_arg("wcShowUpdateMessage", &self.status);
                }
                self.update_manual = false;
                app.status(self.status.clone());
                ctx.request_repaint();
            } else {
                // GitHub I/O is asynchronous: keep polling even when the user is idle.
                ctx.request_repaint_after(Duration::from_millis(250));
            }
        }
    }

    // Non-floating, dismissible WordCraft update feedback below the editor.
    // Reserve actual layout space rather than obscuring ribbon, text or dialogs.
    pub fn update_feedback(&mut self, ui: &mut egui::Ui) {
        if !self.update_visible { return; }
        egui::Panel::bottom("wc_update_feedback").show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                if self.update_checking { ui.spinner(); }
                ui.label(&self.update_message);
                if !self.update_checking {
                    if let Some(url) = self.release_url.clone() {
                        if ui.button("View WordCraft release").clicked() {
                            if let Err(error) = self.call_string_arg("wcOpenUpdatePage", &url) {
                                self.update_message = format!("Could not open release page: {error}");
                            }
                        }
                    }
                }
                if ui.button("Dismiss").clicked() {
                    self.update_visible = false;
                }
            });
        });
    }

    pub fn prepare_menu(&self, ctx: &egui::Context, frame: &eframe::Frame) {
        // WC_ANDROID_STYLUS_INPUT_V1: lightweight Java status snapshot at most every
        // 300 ms, never interrupting the Draw tab or the touch/trackpad pipeline.
        let probe_id = egui::Id::new("wc_stylus_probe_at");
        let probe = ctx.data(|d| d.get_temp::<Instant>(probe_id)
            .is_none_or(|when| when.elapsed() >= Duration::from_millis(300)));
        if probe {
            let status = self.call_string("wcStylusStatus").ok().flatten()
                .unwrap_or_else(|| "Stylus: Android status unavailable".to_owned());
            ctx.data_mut(|d| {
                d.insert_temp(probe_id, Instant::now());
                d.insert_temp(egui::Id::new("wc_menu_stylus_status"), status);
            });
        }
        let gpu = if let Some(render) = frame.wgpu_render_state() {
            let info = render.adapter.get_info();
            format!("GPU: {} ({:?})", info.name, info.backend)
        } else {
            "GPU: renderer information not available".to_owned()
        };
        ctx.data_mut(|d| {
            d.insert_temp(egui::Id::new("wc_menu_font_busy"), self.fonts.busy);
            d.insert_temp(egui::Id::new("wc_menu_startup"), self.startup_updates);
            d.insert_temp(egui::Id::new("wc_menu_pad"), self.show_pad);
            d.insert_temp(egui::Id::new("wc_menu_status"), self.status.clone());
            d.insert_temp(egui::Id::new("wc_menu_release"), self.release_url.clone().unwrap_or_default());
            d.insert_temp(egui::Id::new("wc_menu_gpu"), gpu);
        });
    }

    pub fn ui(
        &mut self,
        app: &mut wordcraft_ui_egui::WordApp,
        ctx: &egui::Context,
        _frame: &mut eframe::Frame,
    ) {
        let action = ctx.data_mut(|d| {
            let id = egui::Id::new("wc_menu_action");
            let value = d.get_temp::<String>(id).unwrap_or_default();
            d.insert_temp(id, String::new());
            value
        });
        match action.as_str() {
            "font_import" | "font_folder" | "font_refresh" if !self.fonts.busy => {
                self.pending_fonts.clear();
                self.status = self.fonts.start();
                let method = match action.as_str() {
                    "font_import" => "wcImportFonts",
                    "font_folder" => "wcRequestFontFolder",
                    _ => "wcRefreshFontFolder",
                };
                if let Err(error) = self.call_void(method) {
                    self.status = self.fonts.stop(format!("Font folder error: {error}"));
                } else if action == "font_folder" {
                    self.status = "Choose your shared font folder in Android Files".into();
                } else if action == "font_import" {
                    self.status = "Select TTF / OTF fonts in Android Files".into();
                }
                app.status(self.status.clone());
                ctx.request_repaint_after(Duration::from_millis(100));
            }
            "check_updates" => {
                self.update_visible = true;
                self.release_url = None;
                if self.update_checking {
                    self.status = "Already checking WordCraft Android releases...".into();
                } else {
                    match self.call_void("wcCheckForUpdates") {
                        Ok(()) => {
                            self.update_checking = true;
                            self.update_manual = true;
                            self.update_started = Some(Instant::now());
                            self.status = "Checking published WordCraft Android APK releases...".into();
                        }
                        Err(error) => {
                            self.status = format!("Update check error: {error}");
                            self.update_checking = false;
                            self.update_manual = false;
                            self.update_started = None;
                        }
                    }
                }
                self.update_message = self.status.clone();
                let _ = self.call_string_arg("wcShowUpdateMessage", &self.status);
                app.status(self.status.clone());
                ctx.request_repaint_after(Duration::from_millis(250));
            },
            "startup_on" | "startup_off" => {
                self.startup_updates = action == "startup_on";
                if let Err(error) = self.call_bool_arg("wcSetStartupUpdates", self.startup_updates) {
                    self.status = format!("Could not save update preference: {error}");
                }
            }
            "view_release" => {
                if let Some(url) = &self.release_url {
                    if let Err(error) = self.call_string_arg("wcOpenUpdatePage", url) {
                        self.status = format!("Could not open release page: {error}");
                    }
                }
            }
            // WC_GC_STYLE_APPEARANCE_V1: WordCraft's own upstream UI commands
            // persist ui.theme in ui.json; never mistake page inversion for UI theme.
            "theme_system" | "theme_light" | "theme_dark" => {
                let value = action.strip_prefix("theme_").unwrap_or("system");
                match app.run("ui.theme", serde_json::json!({"value": value})) {
                    Ok(_) => self.status = format!("Interface theme: {value}"),
                    Err(error) => self.status = format!("Could not change theme: {error}"),
                }
            }
            "page_dark_on" | "page_dark_off" => {
                let value = action == "page_dark_on";
                match app.run("view.darkMode", serde_json::json!({"value": value})) {
                    Ok(_) => self.status = if value {
                        "Document pages: dark".to_owned()
                    } else {
                        "Document pages: normal".to_owned()
                    },
                    Err(error) => self.status = format!("Could not change page mode: {error}"),
                }
            }
            "pad_on" => self.show_pad = true,
            "pad_off" => self.show_pad = false,
            "keyboard" => self.status = match app.run("tools.customizeKeyboard", serde_json::json!({})) {
                Ok(_) => "Customize Keyboard dialog opened".into(),
                Err(error) => format!("Keyboard customization: {error}"),
            },
            _ => {}
        }
        // Snapshot actual upstream state, not a second Android preference.
        // Next Wc menu open reflects File > Options / View > Interface Theme too.
        ctx.data_mut(|d| {
            d.insert_temp(
                egui::Id::new("wc_menu_interface_theme"),
                app.ui.theme.code().to_owned()
            );
            d.insert_temp(egui::Id::new("wc_menu_dark_page"), app.session.view.dark_mode);
        });
        if !action.is_empty() { ctx.request_repaint(); }
        if self.show_pad {
            let mut open = self.show_pad;
            egui::Window::new("WordCraft Shortcut Pad")
                .id(egui::Id::new("wc_shortcut_pad"))
                .open(&mut open)
                .default_width(290.0)
                .show(ctx, |ui| {
                    ui.label("Tap a command; change each slot with the dropdown.");
                    for row in 0..3 {
                        ui.horizontal(|ui| {
                            for col in 0..2 {
                                let slot = row * 2 + col;
                                let mut selected = self.slots[slot];
                                egui::ComboBox::from_id_salt(("wc_pad_slot", slot))
                                    .selected_text(ACTIONS[selected].0)
                                    .width(95.0)
                                    .show_ui(ui, |ui| {
                                        for (index, (label, _)) in ACTIONS.iter().enumerate() {
                                            ui.selectable_value(&mut selected, index, *label);
                                        }
                                    });
                                if selected != self.slots[slot] {
                                    self.slots[slot] = selected;
                                    self.save_pad();
                                }
                                if ui.button("Run").clicked() {
                                    let (label, command) = ACTIONS[self.slots[slot]];
                                    match app.run(command, serde_json::json!({})) {
                                        Ok(_) => self.status = format!("{label} executed"),
                                        Err(error) => self.status = format!("{label}: {error}"),
                                    }
                                }
                            }
                        });
                    }
                    ui.label(&self.status);
                });
            self.show_pad = open;
        }
    }
}

