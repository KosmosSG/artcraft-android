//! Android native update feedback and EffectCraft text-engine font registration.
use android_activity::AndroidApp;
use jni::{jni_sig, jni_str, JavaVM, objects::{JObject, JString, JValue}};
use std::sync::mpsc;

pub struct Updater {
    app: AndroidApp,
    started: bool,
    fonts: mpsc::Sender<String>,
    reports: mpsc::Receiver<String>,
}

macro_rules! action {
    ($self:expr, $name:literal) => {{
        let vm = unsafe { JavaVM::from_raw($self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = $self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!($name), jni_sig!("()V"), &[]);
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        }).map_err(|e| e.to_string())
    }};
}

impl Updater {
    pub fn new(app: &AndroidApp) -> Self {
        let (sender, receiver) = mpsc::channel::<String>();
        let (report_tx, reports) = mpsc::channel();
        let root = app.internal_data_path().map(|p| p.join("custom-fonts"));
        std::thread::spawn(move || {
            let mut loaded = std::collections::HashSet::new();
            for path in receiver {
                let result = (|| -> Result<usize, String> {
                    let file = std::path::PathBuf::from(&path);
                    let root = root.as_ref().ok_or("Private font storage unavailable")?;
                    if file.parent() != Some(root.as_path()) { return Err("Untrusted font path".into()); }
                    if loaded.contains(&path) { return Ok(0); }
                    let meta = std::fs::metadata(&file).map_err(|e| e.to_string())?;
                    if !meta.is_file() || meta.len() > 32 * 1024 * 1024 { return Err("Invalid font file size".into()); }
                    let bytes = std::fs::read(&file).map_err(|e| e.to_string())?;
                    let count = effectcraft_text::fonts::add_font_data(bytes).len();
                    if count == 0 {
                        let _ = std::fs::remove_file(&file);
                        return Err("Font has no supported faces".into());
                    }
                    loaded.insert(path.clone());
                    Ok(count)
                })();
                if let Err(error) = result { let _ = report_tx.send(error); }
            }
        });
        Self { app: app.clone(), started: false, fonts: sender, reports }
    }

    fn font_path(&self) -> Result<Option<String>, String> {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("ecPollFontPath"), jni_sig!("()Ljava/lang/String;"), &[]);
            if result.is_err() { env.exception_clear(); }
            let value = result?.l()?;
            if value.is_null() { return Ok(None); }
            Ok(Some(JString::cast_local(env, value)?.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn message(&self, message: &str) {
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let _ = vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let string = JObject::from(env.new_string(message)?);
            let result = env.call_method(&*activity, jni_str!("ecFontMessage"), jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&string)]);
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        });
    }

    pub fn poll(&mut self, ctx: &egui::Context) {
        if !self.started {
            self.started = true;
            if let Err(e) = action!(self, "ecInitialize") { self.message(&e); }
        }
        for _ in 0..8 {
            match self.font_path() {
                Ok(Some(path)) => { let _ = self.fonts.send(path); }
                _ => break,
            }
        }
        while let Ok(report) = self.reports.try_recv() { self.message(&report); }
        ctx.request_repaint_after(std::time::Duration::from_millis(500));
    }

    pub fn ui(&mut self, ctx: &egui::Context) {
        macro_rules! dispatch {
            ($key:literal, $method:literal) => {
                if ctx.data_mut(|d| d.remove_temp::<bool>(egui::Id::new($key))).unwrap_or(false) {
                    if let Err(e) = action!(self, $method) { self.message(&e); }
                }
            };
        }
        dispatch!("artcraft.effectcraft.check_updates_requested", "ecCheckForUpdates");
        dispatch!("artcraft.effectcraft.update_settings_requested", "ecStartupUpdateSettings");
        dispatch!("artcraft.effectcraft.import_font", "ecImportFont");
        dispatch!("artcraft.effectcraft.select_fonts", "ecSelectSharedFonts");
        dispatch!("artcraft.effectcraft.refresh_fonts", "ecRefreshFonts");
    }
}
