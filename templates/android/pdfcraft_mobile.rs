//! PDFCraft Android-only, docked controls. Kept separate from the upstream PDF engine.
//! File-import and update actions are handled by Android's Java Activity; no auto installation.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};
use serde_json::Value;

#[derive(Clone, Copy)]
enum Action { ImportFont, SelectFolder, RefreshFonts, CheckUpdates }

pub struct Mobile {
    app: AndroidApp,
    renderer: String,
    fonts_open: bool,
    updates_open: bool,
    font_status: String,
    update_status: String,
    update_url: Option<String>,
    checking: bool,
    startup_check: bool,
    first_frame: bool,
}

impl Mobile {
    pub fn new(app: AndroidApp) -> Self {
        let mut mobile = Self {
            app, renderer: "Renderer not initialized".into(), fonts_open: false, updates_open: false,
            font_status: "PDF text fonts: none imported this session".into(),
            update_status: "No update check has run yet".into(),
            update_url: None, checking: false, startup_check: false, first_frame: true,
        };
        mobile.startup_check = mobile.read_startup_setting().unwrap_or(false);
        mobile
    }

    fn read_startup_setting(&self) -> Result<bool, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfStartupUpdateEnabled"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|err| err.to_string())
    }
    fn save_startup_setting(&self, enabled: bool) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pdfSetStartupUpdateEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    fn request(&self, action: Action) -> Result<(), String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            match action {
                Action::ImportFont => {
                    env.call_method(&*activity, jni_str!("pdfRequestFont"), jni_sig!("()V"), &[])?;
                }
                Action::SelectFolder => {
                    env.call_method(&*activity, jni_str!("pdfRequestFontFolder"), jni_sig!("()V"), &[])?;
                }
                Action::RefreshFonts => {
                    env.call_method(&*activity, jni_str!("pdfRefreshFontFolder"), jni_sig!("()V"), &[])?;
                }
                Action::CheckUpdates => {
                    env.call_method(&*activity, jni_str!("pdfCheckForUpdates"), jni_sig!("()V"), &[])?;
                }
            }
            Ok(())
        }).map_err(|err| err.to_string())
    }
    fn poll_java(&self, updates: bool) -> Result<Option<String>, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let v = if updates {
                env.call_method(&*activity, jni_str!("pdfUpdatePoll"),
                    jni_sig!("()Ljava/lang/String;"), &[])?.l()?
            } else {
                env.call_method(&*activity, jni_str!("pdfFontPoll"),
                    jni_sig!("()Ljava/lang/String;"), &[])?.l()?
            };
            if v.is_null() { return Ok(None); }
            let s = JString::cast_local(env, v)?;
            Ok(Some(s.try_to_string(env)?))
        }).map_err(|err| err.to_string())
    }
    fn release_page(&self, url: &str) -> Result<(), String> {
        if !url.starts_with("https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v") {
            return Err("Release page is not an approved PDFCraft Android release".into());
        }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let address = JObject::from(env.new_string(url)?);
            env.call_method(&*activity, jni_str!("pdfOpenReleasePage"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&address)])?;
            Ok(())
        }).map_err(|err| err.to_string())
    }
    pub fn do_update_check(&mut self) {
        if self.checking { return; }
        self.update_url = None;
        self.update_status = "Checking published PDFCraft Android releases…".into();
        self.updates_open = true;
        match self.request(Action::CheckUpdates) {
            Ok(()) => self.checking = true,
            Err(error) => self.update_status = format!("Update checker unavailable: {error}"),
        }
    }
    pub fn poll(&mut self, ctx: &egui::Context) {
        if self.first_frame {
            self.first_frame = false;
            if self.startup_check { self.do_update_check(); }
        }
        for _ in 0..8 {
            match self.poll_java(false) {
                Ok(Some(payload)) => {
                    self.font_status = serde_json::from_str::<Value>(&payload).ok()
                        .and_then(|v| v.get("message").and_then(Value::as_str).map(str::to_owned))
                        .unwrap_or_else(|| "Unrecognized font result".to_owned());
                    ctx.request_repaint();
                }
                Ok(None) => break,
                Err(error) => { self.font_status = format!("Font bridge: {error}"); break; }
            }
        }
        if self.checking {
            match self.poll_java(true) {
                Ok(Some(payload)) => {
                    self.checking = false;
                    if let Ok(response) = serde_json::from_str::<Value>(&payload) {
                        self.update_status = response.get("message").and_then(Value::as_str)
                            .unwrap_or("Invalid GitHub release response").into();
                        self.update_url = response.get("url").and_then(Value::as_str)
                            .filter(|u| u.starts_with(
                                "https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v"))
                            .map(str::to_owned);
                    } else {
                        self.update_status = "Invalid update response".into();
                    }
                    ctx.request_repaint();
                }
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(250)),
                Err(error) => {
                    self.checking = false;
                    self.update_status = format!("Update checker: {error}");
                }
            }
        }
    }
    pub fn set_renderer(&mut self, description: String) { self.renderer = description; }
    pub fn toolbar(&mut self, parent: &mut egui::Ui) {
        egui::Panel::bottom("pdfcraft_android_tools").resizable(false).show(parent, |ui| {
            ui.horizontal_wrapped(|ui| {
                if ui.button(if self.fonts_open { "Fonts ▴" } else { "Fonts ▾" }).clicked() {
                    self.fonts_open = !self.fonts_open;
                }
                if ui.button("Check updates").clicked() { self.do_update_check(); }
                ui.separator();
                ui.label("PDFCraft Android • document fonts and releases").on_hover_text(&self.renderer);
            });
            if self.fonts_open {
                ui.separator();
                ui.horizontal_wrapped(|ui| {
                    if ui.button("Import TTF/OTF").clicked() {
                        self.font_status = "Choose a .ttf or .otf font…".into();
                        if let Err(error) = self.request(Action::ImportFont) { self.font_status = error; }
                    }
                    if ui.button("Select shared ArtCraft-Fonts folder").clicked() {
                        self.font_status = "Choose your shared Android font directory…".into();
                        if let Err(error) = self.request(Action::SelectFolder) { self.font_status = error; }
                    }
                    if ui.button("Refresh shared folder").clicked() {
                        self.font_status = "Refreshing previously selected folder…".into();
                        if let Err(error) = self.request(Action::RefreshFonts) { self.font_status = error; }
                    }
                });
                ui.label(&self.font_status);
                ui.label(egui::RichText::new("Only embeddable fonts accepted by PDFCraft are available for PDF text tools; existing embedded fonts are unchanged.").small());
            }
            if self.updates_open {
                ui.separator();
                ui.horizontal_wrapped(|ui| {
                    ui.label(&self.update_status);
                    if self.checking { ui.spinner(); }
                    if let Some(url) = self.update_url.clone() {
                        if ui.button("View GitHub release").clicked() {
                            if let Err(error) = self.release_page(&url) { self.update_status = error; }
                        }
                    }
                    if ui.button("Hide").clicked() { self.updates_open = false; }
                });
                if ui.checkbox(&mut self.startup_check, "Check for PDFCraft Android updates at startup").changed() {
                    if let Err(error) = self.save_startup_setting(self.startup_check) {
                        self.update_status = format!("Could not save startup preference: {error}");
                    }
                }
                ui.label(egui::RichText::new("Checks only published PDFCraft Android APKs; never installs automatically.").small());
            }
        });
    }
}
