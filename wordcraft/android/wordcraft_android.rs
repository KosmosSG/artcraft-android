//! WordCraft-only Android UI and JNI extensions.
//! No signing, APK downloading, silent installs or broad storage permissions.
use android_activity::AndroidApp;
use eframe::egui;
use jni::{JavaVM, jni_sig, strings::JNIString, objects::{JObject, JString, JValue}};
use serde_json::Value;
use std::collections::VecDeque;
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
}

impl Tools {
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
        };
        tools.startup_updates = tools.call_bool("wcStartupUpdates").unwrap_or(false);
        if let Ok(Some(saved)) = tools.call_string("wcGetShortcutPad") {
            for (i, id) in saved.split(',').take(6).enumerate() {
                if let Some(index) = ACTIONS.iter().position(|(_, command)| *command == id) {
                    tools.slots[i] = index;
                }
            }
        }
        if tools.startup_updates && tools.call_void("wcCheckForUpdates").is_ok() {
            tools.update_checking = true;
            tools.update_started = Some(Instant::now());
        }
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
        for _ in 0..2 {
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
    pub fn update_feedback(&mut self, ctx: &egui::Context) {
        if !self.update_visible { return; }
        egui::TopBottomPanel::bottom("wc_update_feedback").show(ctx, |ui| {
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
            "font_folder" | "font_refresh" if !self.fonts.busy => {
                self.pending_fonts.clear();
                self.status = self.fonts.start();
                let method = if action == "font_folder" { "wcRequestFontFolder" } else { "wcRefreshFontFolder" };
                if let Err(error) = self.call_void(method) {
                    self.status = self.fonts.stop(format!("Font folder error: {error}"));
                } else if action == "font_folder" {
                    self.status = "Choose your shared font folder in Android Files".into();
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
            "pad_on" => self.show_pad = true,
            "pad_off" => self.show_pad = false,
            "keyboard" => self.status = match app.run("tools.customizeKeyboard", serde_json::json!({})) {
                Ok(_) => "Customize Keyboard dialog opened".into(),
                Err(error) => format!("Keyboard customization: {error}"),
            },
            _ => {}
        }
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

