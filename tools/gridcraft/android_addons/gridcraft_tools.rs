//! GRIDCRAFT_ANDROID_TOOLS_V1 — shell-only enhancements; upstream spreadsheet crates unchanged.
//! Java owns SAF folder grants and network IO; this module only drives the native UI via JNI.
//! Font catalog uses OnceLock in GridCraft v0.9.0, so reload requires restarting the app.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};
use std::sync::Arc;

pub struct GridCraftTools {
    app: AndroidApp,
    vm: Arc<JavaVM>,
    pub font_status: String,
    pub update_status: String,
    release_url: Option<String>,
    startup_loaded: bool,
    startup_check: bool,
    show_shortcut_pad: bool,
}
impl GridCraftTools {
    pub fn new(app: &AndroidApp) -> Self {
        // SAFETY: AndroidApp owns this live JavaVM for the lifetime of the native activity.
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        Self {
            app: app.clone(), vm: Arc::new(vm),
            font_status: "Import TTF/OTF or choose ArtCraft-Fonts (restart to apply).".into(),
            update_status: "Manual update check available; no automatic APK installation.".into(),
            release_url: None, startup_loaded: false, startup_check: false,
            show_shortcut_pad: false,
        }
    }
    fn send(&self, action: Action) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            // SAFETY: The activity global reference belongs to AndroidApp; this is a borrowed JNI view.
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = match action {
                Action::Import => env.call_method(&*activity, jni_str!("gcImportFont"), jni_sig!("()V"), &[]),
                Action::SelectFolder => env.call_method(&*activity, jni_str!("gcSelectSharedFolder"), jni_sig!("()V"), &[]),
                Action::RefreshFolder => env.call_method(&*activity, jni_str!("gcRefreshSharedFolder"), jni_sig!("()V"), &[]),
                Action::CheckUpdates => env.call_method(&*activity, jni_str!("gcCheckForUpdates"), jni_sig!("()V"), &[]),
            };
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        }).map_err(|e| format!("Android integration unavailable: {e}"))
    }
    fn read_startup(&self) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("gcStartupChecksEnabled"), jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| format!("Cannot read update preference: {e}"))
    }
    fn write_startup(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("gcSetStartupChecks"), jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| format!("Cannot save update preference: {e}"))
    }
    fn open_release(&self, url: &str) -> Result<(), String> {
        if !url.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/gridcraft-v") {
            return Err("The release link is not an official GridCraft URL".into());
        }
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let name = JObject::from(env.new_string(url)?);
            env.call_method(&*activity, jni_str!("gcOpenUpdatePage"), jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&name)])?;
            Ok(())
        }).map_err(|e| format!("Cannot open release page: {e}"))
    }
    fn read_result(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("gcPollResult"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(None); }
            let value = JString::cast_local(env, value)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| format!("Cannot poll GridCraft Android tools: {e}"))
    }
    pub fn poll(&mut self) {
        if !self.startup_loaded {
            match self.read_startup() {
                Ok(value) => { self.startup_check = value; self.startup_loaded = true; },
                Err(err) => { self.update_status = err; self.startup_loaded = true; },
            }
        }
        for _ in 0..4 {
            let event = match self.read_result() {
                Ok(Some(event)) => event,
                Ok(None) => break,
                Err(err) => { self.update_status = err; break; },
            };
            match serde_json::from_str::<serde_json::Value>(&event) {
                Ok(value) => {
                    let text = value.get("message").and_then(|v| v.as_str()).unwrap_or("No further detail").to_string();
                    match value.get("kind").and_then(|v| v.as_str()).unwrap_or_default() {
                        "font" | "folder" => self.font_status = text,
                        "update" => {
                            self.update_status = text;
                            self.release_url = value.get("url").and_then(|v| v.as_str())
                                .filter(|s| s.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/gridcraft-v"))
                                .map(str::to_owned);
                        }
                        _ => log::warn!("Unexpected GridCraft Android event kind"),
                    }
                }
                Err(error) => self.update_status = format!("Invalid Android result: {error}"),
            }
        }
    }
    fn try_action(&mut self, action: Action) {
        let result = self.send(action);
        match result {
            Ok(()) => {
                if matches!(action, Action::CheckUpdates) {
                    self.release_url = None;
                    self.update_status = "Checking published GridCraft Android releases…".into();
                } else {
                    self.font_status = "Waiting for Android Files…".into();
                }
            }
            Err(err) => {
                if matches!(action, Action::CheckUpdates) { self.update_status = err; }
                else { self.font_status = err; }
            }
        }
    }
    /// Non-floating Android controls in the app's existing egui host; not a separate font window.
    pub fn ui(&mut self, ui: &mut egui::Ui, sheet: &mut gridcraft_ui_egui::SheetApp) {
        ui.collapsing("GridCraft Android: Fonts, Updates & Shortcuts", |ui| {
            ui.horizontal_wrapped(|ui| {
                if ui.button("Import TTF / OTF").clicked() { self.try_action(Action::Import); }
                if ui.button("Select Shared Font Folder").clicked() { self.try_action(Action::SelectFolder); }
                if ui.button("Refresh Shared Fonts").clicked() { self.try_action(Action::RefreshFolder); }
            });
            ui.label(&self.font_status);
            ui.separator();
            if ui.button("Check for GridCraft Updates").clicked() { self.try_action(Action::CheckUpdates); }
            if let Some(url) = self.release_url.clone() {
                if ui.button("View verified GitHub release").clicked() {
                    if let Err(error) = self.open_release(&url) { self.update_status = error; }
                }
            }
            ui.label(&self.update_status);
            let mut startup = self.startup_check;
            if ui.checkbox(&mut startup, "Check for updates at startup").changed() {
                match self.write_startup(startup) {
                    Ok(()) => { self.startup_check = startup; self.update_status = "Startup preference saved.".into(); }
                    Err(error) => self.update_status = error,
                }
            }
            ui.separator();
            ui.checkbox(&mut self.show_shortcut_pad, "Show tablet Shortcut Pad");
            if self.show_shortcut_pad {
                ui.horizontal_wrapped(|ui| {
                    for (label, command) in [
                        ("Undo", "edit.undo"), ("Redo", "edit.redo"),
                        ("Previous sheet", "sheet.previous"), ("Next sheet", "sheet.next"),
                    ] {
                        if ui.button(label).clicked() {
                            if let Err(error) = sheet.run(command, serde_json::json!({})) {
                                self.font_status = format!("{label}: {error}");
                            }
                        }
                    }
                    let zoom = sheet.session.active()
                        .and_then(|d| d.wb.active().map(|s| s.zoom))
                        .unwrap_or(100);
                    for (label, value) in [
                        ("Zoom −", (i32::from(zoom) - 10).clamp(10, 400)),
                        ("Zoom +", (i32::from(zoom) + 10).clamp(10, 400))
                    ] {
                        if ui.button(label).clicked() {
                            if let Err(error) = sheet.run("view.zoom", serde_json::json!({"percent": value})) {
                                self.font_status = format!("{label}: {error}");
                            }
                        }
                    }
                });
            }
            ui.small("GPU: renderer/backend not verified on this device; do not infer acceleration from the model name.");
        });
    }
}
#[derive(Clone, Copy)]
enum Action { Import, SelectFolder, RefreshFolder, CheckUpdates }
