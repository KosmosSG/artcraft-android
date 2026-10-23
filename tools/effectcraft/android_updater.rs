//! Android-only EffectCraft updater: PhotoCraft-style manual GitHub Releases check.
//! The Java Activity performs bounded async HTTPS I/O. The user chooses the APK,
//! Android verifies package/certificate at install time. Never silently install.
use android_activity::AndroidApp;
use jni::{jni_sig, jni_str, JavaVM, objects::{JObject, JString}};

const RELEASE_ROOT: &str = "https://github.com/KosmosSG/artcraft-android/releases/tag/effectcraft-v";
const ASSET_ROOT: &str = "https://github.com/KosmosSG/artcraft-android/releases/download/effectcraft-v";

pub struct Updater {
    app: AndroidApp,
    open: bool,
    checking: bool,
    startup_pending: bool,
    automatic: bool,
    message: String,
    release_url: Option<String>,
    download_url: Option<String>,
}

impl Updater {
    pub fn new(app: &AndroidApp) -> Self {
        Self {
            app: app.clone(), open: false, checking: false, startup_pending: true, automatic: false,
            message: String::new(), release_url: None, download_url: None,
        }
    }

    fn check_java(&self) -> Result<(), String> {
        // SAFETY: AndroidApp retains the VM and activity for the lifetime of this shell.
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let response = env.call_method(&*activity, jni_str!("ecCheckForUpdates"), jni_sig!("()V"), &[]);
            if response.is_err() { env.exception_clear(); }
            response?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn settings_java(&self) -> Result<(), String> {
        // SAFETY: AndroidApp retains the VM and activity for the lifetime of this shell.
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let response = env.call_method(&*activity, jni_str!("ecStartupUpdateSettings"), jni_sig!("()V"), &[]);
            if response.is_err() { env.exception_clear(); }
            response?;
            Ok(())
        }).map_err(|e| e.to_string())
    }


    fn startup_enabled(&self) -> bool {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("ecStartupUpdatesEnabled"), jni_sig!("()Z"), &[]);
            if result.is_err() { env.exception_clear(); }
            result?.z()
        }).unwrap_or(false)
    }

    fn poll_java(&self) -> Result<Option<String>, String> {
        // SAFETY: same live AndroidApp object as the UI frame.
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let response = match env.call_method(
                &*activity, jni_str!("ecPollUpdateResult"),
                jni_sig!("()Ljava/lang/String;"), &[]
            ) {
                Ok(value) => value.l()?,
                Err(err) => { env.exception_clear(); return Err(err); }
            };
            if response.is_null() { return Ok(None); }
            let string = JString::cast_local(env, response)?;
            Ok(Some(string.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    pub fn poll(&mut self, ctx: &egui::Context) {
        if self.startup_pending {
            self.startup_pending = false;
            if self.startup_enabled() && self.check_java().is_ok() {
                self.checking = true;
                self.automatic = true;
            }
        }
        if !self.checking { return; }
        match self.poll_java() {
            Ok(None) => { ctx.request_repaint_after(std::time::Duration::from_millis(300)); }
            Err(err) => {
                self.checking = false;
                self.message = format!("Update checker unavailable: {err}");
            }
            Ok(Some(json)) => {
                self.checking = false;
                let response = serde_json::from_str::<serde_json::Value>(&json);
                match response {
                    Err(err) => self.message = format!("Invalid GitHub update response: {err}"),
                    Ok(info) => {
                        if self.automatic && info["state"].as_str() == Some("update_available") {
                            self.open = true;
                        }
                        let installed = info["installed_version"].as_str().unwrap_or("unknown");
                        let latest = info["latest_version"].as_str().unwrap_or("none");
                        self.release_url = info["release_url"].as_str()
                            .filter(|u| u.starts_with(RELEASE_ROOT))
                            .map(ToOwned::to_owned);
                        self.download_url = info["download_url"].as_str()
                            .filter(|u| u.starts_with(ASSET_ROOT)
                                && u.ends_with("-arm64-v8a.apk"))
                            .map(ToOwned::to_owned);
                        self.message = match info["state"].as_str() {
                            Some("update_available") if self.release_url.is_some() && self.download_url.is_some() =>
                                format!("Update available: {latest} (installed: {installed}). Download the official APK to update without uninstalling."),
                            Some("update_available") =>
                                "Update release metadata failed its URL validation. No download offered.".to_owned(),
                            Some("up_to_date") =>
                                format!("EffectCraft is up to date (installed: {installed}; latest: {latest})."),
                            Some("no_release") =>
                                "No published EffectCraft Android APK release found yet.".to_owned(),
                            _ => format!("Could not check updates: {}",
                                info["message"].as_str().unwrap_or("Unexpected response")),
                        };
                    }
                }
                ctx.request_repaint();
            }
        }
    }

    pub fn ui(&mut self, ctx: &egui::Context) {
        let settings = ctx.data_mut(|d|
            d.remove_temp::<bool>(egui::Id::new("artcraft.effectcraft.update_settings_requested"))
        ).unwrap_or(false);
        if settings {
            if let Err(err) = self.settings_java() {
                self.open = true;
                self.message = format!("Could not open update settings: {err}");
            }
        }
        let requested = ctx.data_mut(|d|
            d.remove_temp::<bool>(egui::Id::new("artcraft.effectcraft.check_updates_requested"))
        ).unwrap_or(false);
        if requested && !self.checking {
            self.automatic = false;
            self.open = true;
            self.message = "Checking official EffectCraft GitHub releases…".to_owned();
            self.download_url = None;
            self.release_url = None;
            match self.check_java() {
                Ok(()) => self.checking = true,
                Err(err) => self.message = format!("Could not start update check: {err}"),
            }
        }

        if !self.open { return; }
        let mut open = self.open;
        egui::Window::new("EffectCraft Updates")
            .open(&mut open)
            .show(ctx, |ui| {
                ui.label(&self.message);
                if self.checking {
                    ui.spinner();
                } else {
                    if let Some(url) = self.release_url.as_ref() {
                        ui.hyperlink_to("View official GitHub Release", url);
                    }
                    if let Some(url) = self.download_url.as_ref() {
                        ui.hyperlink_to("Download EffectCraft ARM64 APK", url);
                        ui.label("Android will ask you to confirm installation. Only an APK with the same package and original EffectCraft signing certificate can update the installed app.");
                    }
                }
            });
        self.open = open;
    }
}
