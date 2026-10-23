//! LightCraft-only Android release checker. Same manual GitHub Releases model as
//! PhotoCraft; package, signing key and current installed version remain untouched.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};

#[derive(Default)]
pub struct Updater {
    open: bool,
    checking: bool,
    message: String,
    release_page: Option<String>,
    initialized: bool,
    startup_enabled: bool,
    settings_open: bool,
    background_check: bool,
}

impl Updater {
    fn check(app: &AndroidApp) -> Result<(), String> {
        // SAFETY: AndroidApp owns the Java VM and global Activity reference.
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("lcCheckForUpdates"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn poll(app: &AndroidApp) -> Result<Option<String>, String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity,
                jni_str!("lcPollUpdateResult"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() {
                Ok(None)
            } else {
                let value = JString::cast_local(env, result)?;
                Ok(Some(value.try_to_string(env)?))
            }
        }).map_err(|e| e.to_string())
    }

    fn startup_preference(app: &AndroidApp) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("lcGetStartupUpdateCheck"), jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }

    fn persist_startup_preference(app: &AndroidApp, enabled: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("lcSetStartupUpdateCheck"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn begin_check(&mut self, app: &AndroidApp, background: bool) {
        self.background_check = background;
        self.checking = true;
        self.message = "Checking official LightCraft GitHub Releases…".into();
        self.release_page = None;
        if let Err(e) = Self::check(app) {
            self.checking = false;
            self.background_check = false;
            if !background {
                self.message = format!("Cannot start update check: {e}");
            }
        }
    }

    fn open_page(app: &AndroidApp, url: &str) -> Result<(), String> {
        if !url.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-") {
            return Err("Release URL is not in the approved LightCraft channel".into());
        }
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let url_obj = JObject::from(env.new_string(url)?);
            env.call_method(&*activity, jni_str!("lcOpenUpdatePage"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&url_obj)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    pub fn ui(&mut self, ctx: &egui::Context, app: &AndroidApp) {
        if !self.initialized {
            self.initialized = true;
            match Self::startup_preference(app) {
                Ok(enabled) => {
                    self.startup_enabled = enabled;
                    if enabled { self.begin_check(app, true); }
                }
                Err(e) => {
                    self.startup_enabled = false;
                    self.message = format!("Startup update setting unavailable: {e}");
                }
            }
        }
        let check_id = egui::Id::new("artcraft.lightcraft.check_updates_requested");
        let settings_id = egui::Id::new("artcraft.lightcraft.startup_updates_requested");
        let requested = ctx.data_mut(|d| {
            let flag = d.get_temp::<bool>(check_id).unwrap_or(false);
            if flag { d.insert_temp(check_id, false); }
            flag
        });
        let request_settings = ctx.data_mut(|d| {
            let flag = d.get_temp::<bool>(settings_id).unwrap_or(false);
            if flag { d.insert_temp(settings_id, false); }
            flag
        });
        if request_settings { self.settings_open = true; }
        if requested {
            self.open = true;
            self.begin_check(app, false);
        }
        if self.checking {
            match Self::poll(app) {
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(350)),
                Err(e) => {
                    self.checking = false;
                    if !self.background_check {
                        self.message = format!("Update check failed: {e}");
                    }
                    self.background_check = false;
                }
                Ok(Some(json)) => {
                    self.checking = false;
                    let was_background = self.background_check;
                    self.background_check = false;
                    match serde_json::from_str::<serde_json::Value>(&json) {
                        Err(e) => {
                            if !was_background { self.message = format!("Invalid GitHub response: {e}"); }
                        }
                        Ok(v) => {
                            let installed = v["installed_version"].as_str().unwrap_or("unknown");
                            let latest = v["latest_version"].as_str().unwrap_or("unknown");
                            self.release_page = v["url"].as_str()
                                .filter(|u| u.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-v"))
                                .map(ToString::to_string);
                            let state = v["state"].as_str().unwrap_or("error");
                            if was_background && state != "update_available" {
                                self.release_page = None;
                            } else {
                                self.open = true;
                                self.message = match state {
                                    "update_available" => format!("Update available: {installed} → {latest}"),
                                    "up_to_date" => format!("LightCraft is up to date ({installed})."),
                                    "no_release" => format!("Installed: {installed}. No eligible public LightCraft update yet."),
                                    _ => format!("Could not check releases: {}", v["message"].as_str().unwrap_or("offline or server error")),
                                };
                            }
                        }
                    }
                }
            }
        }
        if self.settings_open {
            let mut is_open = self.settings_open;
            let mut selected = self.startup_enabled;
            egui::Window::new("LightCraft — Startup Update Settings")
                .id(egui::Id::new("lightcraft.android.startup.settings"))
                .collapsible(false).resizable(false)
                .open(&mut is_open).show(ctx, |ui| {
                    ui.checkbox(&mut selected, "Check for updates at startup");
                    ui.small("Off by default. Checks are asynchronous and never stop LightCraft opening.");
                    ui.small("Only eligible published LightCraft releases are offered; no APK is installed automatically.");
                });
            self.settings_open = is_open;
            if selected != self.startup_enabled {
                match Self::persist_startup_preference(app, selected) {
                    Ok(()) => self.startup_enabled = selected,
                    Err(e) => {
                        self.open = true;
                        self.message = format!("Could not save startup preference: {e}");
                    }
                }
            }
        }
        if !self.open { return; }
        let mut is_open = self.open;
        let mut check_again = false;
        let mut show_page = false;
        egui::Window::new("LightCraft — Check for Updates")
            .id(egui::Id::new("lightcraft.android.updates.window"))
            .collapsible(false).resizable(false)
            .open(&mut is_open).show(ctx, |ui| {
                ui.label(&self.message);
                ui.label("Updates are obtained from KosmosSG's official LightCraft GitHub Releases.");
                ui.horizontal(|ui| {
                    if ui.add_enabled(!self.checking, egui::Button::new("Check again")).clicked() {
                        check_again = true;
                    }
                    if self.release_page.is_some() && ui.button("Open GitHub Release").clicked() {
                        show_page = true;
                    }
                });
                ui.small("For safe in-place updates, use a newer versionCode and the same permanent LightCraft signing certificate.");
            });
        self.open = is_open;
        if check_again { self.begin_check(app, false); }
        if show_page {
            if let Some(url) = self.release_page.as_deref() {
                if let Err(e) = Self::open_page(app, url) {
                    self.message = format!("Could not open GitHub: {e}");
                }
            }
        }
    }
}
