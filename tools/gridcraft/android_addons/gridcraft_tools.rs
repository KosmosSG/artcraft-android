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
    checking: bool,
    check_started_at: Option<std::time::Instant>,
    startup_loaded: bool,
    startup_check: bool,
    font_request_pending: bool,
    font_request_started: Option<std::time::Instant>,
    feedback_message: Option<String>,
    feedback_until: Option<std::time::Instant>,
}
impl GridCraftTools {
    pub fn new(app: &AndroidApp) -> Self {
        // SAFETY: AndroidApp owns this live JavaVM for the lifetime of the native activity.
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        Self {
            app: app.clone(), vm: Arc::new(vm),
            font_status: "Import TTF/OTF or choose ArtCraft-Fonts (restart to apply).".into(),
            update_status: "Manual update check available; no automatic APK installation.".into(),
            release_url: None, checking: false, check_started_at: None,
            startup_loaded: false, startup_check: false,
            font_request_pending: false, font_request_started: None,
            feedback_message: None, feedback_until: None,
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
    fn notify(&mut self, message: String) {
        self.feedback_message = Some(message);
        self.feedback_until = Some(std::time::Instant::now() + std::time::Duration::from_secs(7));
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
                        "font" | "folder" => {
                            self.font_request_pending = false;
                            self.font_request_started = None;
                            self.font_status = text.clone();
                            self.notify(text);
                        },
                        "update" => {
                            self.checking = false;
                            self.check_started_at = None;
                            self.update_status = text.clone();
                            self.notify(text);
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
                    self.checking = true;
                    self.check_started_at = Some(std::time::Instant::now());
                    self.notify("Checking GridCraft releases on GitHub…".into());
                } else {
                    self.font_status = "Waiting for Android Files…".into();
                    self.font_request_pending = true;
                    self.font_request_started = Some(std::time::Instant::now());
                    self.notify("Android font picker started…".into());
                }
            }
            Err(err) => {
                if matches!(action, Action::CheckUpdates) {
                    self.checking = false;
                    self.check_started_at = None;
                    self.update_status = err.clone();
                    self.notify(err);
                }
                else {
                    self.font_request_pending = false;
                    self.font_status = err.clone();
                    self.notify(err);
                }
            }
        }
    }
    /// Android data/commands for the native GridCraft Tools top toolbar menu.
    /// The UI's own ribbon embeds that menu without adding a panel or window.
    /// This method is intentionally called before SheetApp::ui: it consumes
    /// menu commands from the prior frame and refreshes the shared menu status.
    pub fn ui(&mut self, ui: &mut egui::Ui, _sheet: &mut gridcraft_ui_egui::SheetApp) {
        let ctx = ui.ctx();
        let command_id = egui::Id::new("gridcraft.android.menu.action");
        let command = ctx.data(|d| d.get_temp::<String>(command_id)).unwrap_or_default();
        if !command.is_empty() {
            ctx.data_mut(|d| d.insert_temp(command_id, String::new()));
            match command.as_str() {
                "import" => self.try_action(Action::Import),
                "folder" => self.try_action(Action::SelectFolder),
                "refresh" => self.try_action(Action::RefreshFolder),
                "updates" => self.try_action(Action::CheckUpdates),
                "open_release" => {
                    if let Some(url) = self.release_url.clone() {
                        if let Err(error) = self.open_release(&url) {
                            self.update_status = error;
                        }
                    }
                }
                "startup_on" | "startup_off" => {
                    let enabled = command == "startup_on";
                    match self.write_startup(enabled) {
                        Ok(()) => {
                            self.startup_check = enabled;
                            self.update_status = "Startup preference saved.".into();
                            self.notify(self.update_status.clone());
                        }
                        Err(error) => {
                            self.update_status = error.clone();
                            self.notify(error);
                        },
                    }
                }
                _ => self.update_status = "Unknown GridCraft Tools menu command.".into(),
            }
        }
        if self.checking {
            if self.check_started_at.is_some_and(|t| t.elapsed() >= std::time::Duration::from_secs(30)) {
                self.checking = false;
                self.check_started_at = None;
                self.release_url = None;
                self.update_status = "Update check timed out. Check your connection and retry.".into();
                self.notify(self.update_status.clone());
            } else {
                ctx.request_repaint_after(std::time::Duration::from_millis(250));
            }
        }
        if self.font_request_pending {
            if self.font_request_started.is_some_and(|t| t.elapsed() >= std::time::Duration::from_secs(60)) {
                self.font_request_pending = false;
                self.font_status = "Font import status timed out. Check the selected file and retry.".into();
                self.notify(self.font_status.clone());
            } else {
                // Java completes SAF imports on a worker thread after the picker closes.
                // Keep polling even while the menu is closed.
                ctx.request_repaint_after(std::time::Duration::from_millis(300));
            }
        }
        if let Some(message) = self.feedback_message.clone() {
            if self.feedback_until.is_some_and(|end| std::time::Instant::now() < end) {
                egui::Area::new(egui::Id::new("gridcraft.android.tools.feedback"))
                    .order(egui::Order::Foreground)
                    .anchor(egui::Align2::RIGHT_TOP, egui::vec2(-12.0, 52.0))
                    .show(ctx, |ui| {
                        egui::Frame::popup(ui.style()).show(ui, |ui| {
                            ui.set_max_width(360.0);
                            ui.label(message);
                        });
                    });
                ctx.request_repaint_after(std::time::Duration::from_millis(250));
            } else {
                self.feedback_message = None;
                self.feedback_until = None;
            }
        }
        // Transient, UI-only state: no workbook document data is changed.
        ctx.data_mut(|d| {
            d.insert_temp(egui::Id::new("gridcraft.android.menu.font_status"), self.font_status.clone());
            d.insert_temp(egui::Id::new("gridcraft.android.menu.update_status"), self.update_status.clone());
            d.insert_temp(egui::Id::new("gridcraft.android.menu.checking"), self.checking);
            d.insert_temp(egui::Id::new("gridcraft.android.menu.startup_check"), self.startup_check);
            d.insert_temp(egui::Id::new("gridcraft.android.menu.has_release"), self.release_url.is_some());
        });
    }
}
#[derive(Clone, Copy)]
enum Action { Import, SelectFolder, RefreshFolder, CheckUpdates }
