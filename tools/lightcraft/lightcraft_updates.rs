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
    include_preview: bool,
    installed_version: String,
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


    fn preview_preference(app: &AndroidApp) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("lcGetIncludePreviewUpdates"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }

    fn persist_preview_preference(app: &AndroidApp, enabled: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("lcSetIncludePreviewUpdates"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn read_installed_version(app: &AndroidApp) -> Result<String, String> {
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        let raw = app.activity_as_ptr() as jni::sys::jobject;
        vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity,
                jni_str!("lcGetInstalledVersion"), jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            let value = JString::cast_local(env, result)?;
            value.try_to_string(env)
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

    /// The native About LightCraft → Updates tab owns all controls and content.
    /// This shell only handles state and asynchronous Android/GitHub I/O.
    /// No separate floating egui::Window is created.
    pub fn ui(&mut self, ctx: &egui::Context, app: &AndroidApp) {
        if !self.initialized {
            self.initialized = true;
            self.installed_version = Self::read_installed_version(app).unwrap_or_else(|_| "unknown".to_string());
            self.include_preview = Self::preview_preference(app).unwrap_or(true);
            match Self::startup_preference(app) {
                Ok(enabled) => {
                    self.startup_enabled = enabled;
                    if enabled { self.begin_check(app, true); }
                }
                Err(error) => {
                    self.startup_enabled = false;
                    self.message = format!("Could not load startup update setting: {error}");
                }
            }
        }

        let trigger_id = egui::Id::new("artcraft.lightcraft.check_updates_requested");
        let changed_id = egui::Id::new("artcraft.lightcraft.startup_changed");
        let desired_id = egui::Id::new("artcraft.lightcraft.startup_desired");
        let open_id = egui::Id::new("artcraft.lightcraft.open_release_requested");
        let channel_changed_id = egui::Id::new("artcraft.lightcraft.channel_changed");
        let channel_desired_id = egui::Id::new("artcraft.lightcraft.channel_desired");
        let (check, changed, desired, open_release, channel_changed, channel_desired) = ctx.data_mut(|d| {
            let check = d.get_temp::<bool>(trigger_id).unwrap_or(false);
            let changed = d.get_temp::<bool>(changed_id).unwrap_or(false);
            let desired = d.get_temp::<bool>(desired_id).unwrap_or(false);
            let open_release = d.get_temp::<bool>(open_id).unwrap_or(false);
            let channel_changed = d.get_temp::<bool>(channel_changed_id).unwrap_or(false);
            let channel_desired = d.get_temp::<bool>(channel_desired_id).unwrap_or(self.include_preview);
            d.insert_temp(trigger_id, false);
            d.insert_temp(changed_id, false);
            d.insert_temp(open_id, false);
            d.insert_temp(channel_changed_id, false);
            (check, changed, desired, open_release, channel_changed, channel_desired)
        });
        if check { self.begin_check(app, false); }
        if changed && desired != self.startup_enabled {
            match Self::persist_startup_preference(app, desired) {
                Ok(()) => self.startup_enabled = desired,
                Err(e) => self.message = format!("Could not save update preference: {e}"),
            }
        }
        if channel_changed && channel_desired != self.include_preview {
            match Self::persist_preview_preference(app, channel_desired) {
                Ok(()) => {
                    self.include_preview = channel_desired;
                    self.message = "Update channel saved. Select Check for Updates to refresh.".into();
                    self.release_page = None;
                }
                Err(e) => self.message = format!("Could not save update channel: {e}"),
            }
        }
        if open_release {
            if let Some(url) = self.release_page.as_deref() {
                if let Err(e) = Self::open_page(app, url) {
                    self.message = format!("Could not open GitHub Release: {e}");
                }
            }
        }
        if self.checking {
            match Self::poll(app) {
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(350)),
                Err(e) => {
                    self.checking = false;
                    self.message = format!("Update check failed: {e}");
                }
                Ok(Some(json)) => {
                    self.checking = false;
                    match serde_json::from_str::<serde_json::Value>(&json) {
                        Err(e) => self.message = format!("Invalid GitHub reply: {e}"),
                        Ok(v) => {
                            let installed = v["installed_version"].as_str().unwrap_or("unknown");
                            let latest = v["latest_version"].as_str().unwrap_or("unknown");
                            self.release_page = v["url"].as_str()
                                .filter(|u| u.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/lightcraft-v"))
                                .map(ToString::to_string);
                            self.message = match v["state"].as_str().unwrap_or("error") {
                                "update_available" => format!("Update available: {installed} → {latest}"),
                                "up_to_date" => format!("LightCraft is up to date ({installed})."),
                                "no_release" => format!("No eligible {} LightCraft release yet.",
                                    if self.include_preview { "stable or preview" } else { "stable" }),
                                _ => format!("Update check unavailable: {}", v["message"].as_str().unwrap_or("network or server error")),
                            };
                        }
                    }
                    ctx.request_repaint();
                }
            }
        }
        ctx.data_mut(|d| {
            d.insert_temp(egui::Id::new("artcraft.lightcraft.update_status"),
                if self.message.is_empty() {
                    "Select Check for Updates to query GitHub Releases.".to_string()
                } else { self.message.clone() });
            d.insert_temp(egui::Id::new("artcraft.lightcraft.startup_enabled"), self.startup_enabled);
            d.insert_temp(egui::Id::new("artcraft.lightcraft.include_preview"), self.include_preview);
            d.insert_temp(egui::Id::new("artcraft.lightcraft.installed_version"), self.installed_version.clone());
            if let Some(url) = self.release_page.as_ref() {
                d.insert_temp(egui::Id::new("artcraft.lightcraft.release_page"), url.clone());
            } else {
                d.insert_temp(egui::Id::new("artcraft.lightcraft.release_page"), String::new());
            }
        });
    }
}
