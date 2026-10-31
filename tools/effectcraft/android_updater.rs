//! Android native update feedback and EffectCraft text-engine font registration.
use android_activity::AndroidApp;
use jni::{jni_sig, jni_str, JavaVM, objects::{JObject, JString, JValue}};
use std::sync::mpsc;

pub struct Updater {
    app: AndroidApp,
    started: bool,
    fonts: mpsc::Sender<(String, bool)>,
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
    pub fn unsaved_dialog(&self, active: bool, ctx: &egui::Context) {
        if !active { ctx.data_mut(|d| d.remove::<u8>(egui::Id::new("effectcraft.unsaved.dcs"))); }
        let vm = unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let result = vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("ecUnsavedDialog"), jni_sig!("(Z)I"), &[JValue::Bool(active.into())]);
            if result.is_err() { env.exception_clear(); }
            result?.i()
        });
        if let Ok(action @ 1..=3) = result {
            if active { ctx.data_mut(|d| d.insert_temp(egui::Id::new("effectcraft.unsaved.dcs"), action as u8)); }
        }
        if active { ctx.request_repaint_after(std::time::Duration::from_millis(16)); }
    }

    pub fn new(app: &AndroidApp) -> Self {
        let (sender, receiver) = mpsc::channel::<(String, bool)>();
        let (report_tx, reports) = mpsc::channel();
        let root = app.internal_data_path().map(|p| p.join("custom-fonts"));
        std::thread::spawn(move || {
            // A canonical path check is needed here: Android may expose the same
            // app-private files directory as /data/data/... or /data/user/0/....
            // Compare resolved paths, and reject symlinks escaping custom-fonts.
            let mut loaded = std::collections::HashMap::<std::path::PathBuf, String>::new();
            for (path, manual) in receiver {
                if let Some(summary) = path.strip_prefix("summary|") {
                    let families: std::collections::BTreeSet<_> = effectcraft_text::fonts::all_faces()
                        .iter().map(|f| f.info.family.clone()).collect();
                    let _ = report_tx.send(format!("{summary}. Catalog: {} registered families. Select in Character or Properties.", families.len()));
                    continue;
                }
                let system = path.starts_with("system|");
                let path = path.strip_prefix("system|").unwrap_or(&path);
                let result = (|| -> Result<String, String> {
                    let root = root.as_ref().ok_or("Private font storage unavailable")?;
                    let root = std::fs::canonicalize(root)
                        .map_err(|e| format!("Font storage unavailable: {e}"))?;
                    let file = std::fs::canonicalize(&path)
                        .map_err(|e| format!("Cannot open imported font: {e}"))?;
                    let system_allowed = ["/system/fonts", "/product/fonts", "/system/product/fonts"].iter()
                        .filter_map(|p| std::fs::canonicalize(p).ok()).any(|p| file.starts_with(p));
                    if !(if system { system_allowed } else { file.parent() == Some(root.as_path()) }) {
                        return Err("Imported font is outside private font storage".into());
                    }
                    if !file.extension().and_then(|x| x.to_str())
                        .is_some_and(|x| x.eq_ignore_ascii_case("ttf") || x.eq_ignore_ascii_case("otf") || x.eq_ignore_ascii_case("ttc")) {
                        return Err("Imported file must be TTF, OTF or TTC".into());
                    }
                    if let Some(family) = loaded.get(&file) {
                        return Ok(format!("Font already available: {family}"));
                    }
                    let meta = std::fs::metadata(&file).map_err(|e| e.to_string())?;
                    if !meta.is_file() || meta.len() < 12 || meta.len() > 64 * 1024 * 1024 {
                        return Err("Invalid font file size".into());
                    }
                    // Name tables are parsed on this worker; full font bytes load lazily for rendering.
                    let faces = effectcraft_text::fonts::android_add_font_file(&file);
                    if faces.is_empty() {
                        // Only delete a verified file directly inside custom-fonts.
                        if !system { let _ = std::fs::remove_file(&file); }
                        return Err("Font engine could not read any faces in this file".into());
                    }
                    let family = effectcraft_text::fonts::face(faces[0]).info.family.clone();
                    loaded.insert(file, family.clone());
                    Ok(format!("Font ready: {family}. Select it in Character or Properties."))
                })();
                match result {
                    Ok(status) if manual => { let _ = report_tx.send(status); }
                    Err(error) => { let _ = report_tx.send(format!("Font import: {error}")); }
                    _ => {}
                }
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
                Ok(Some(path)) => {
                    // The manual marker comes only from the Java file picker; saved
                    // fonts and background shared-folder refreshes stay quiet.
                    let (manual, path) = match path.strip_prefix("manual|") {
                        Some(p) => (true, p.to_owned()),
                        None => (false, path),
                    };
                    if self.fonts.send((path, manual)).is_err() {
                        self.message("Font registration worker stopped");
                        break;
                    }
                }
                Ok(None) => break,
                Err(error) => {
                    self.message(&format!("Font bridge error: {error}"));
                    break;
                },
            }
        }
        while let Ok(report) = self.reports.try_recv() { self.message(&report); ctx.request_repaint(); }
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
