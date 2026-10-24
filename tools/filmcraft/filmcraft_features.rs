//! FilmCraft-only Android toolbar: no separate floating custom-font or update windows.
//! Uses FilmCraft's own font registry, not PhotoCraft's text engine.
use android_activity::AndroidApp;
use jni::{JavaVM, jni_sig, jni_str, objects::{JObject, JString, JValue}};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

const MAX_FONT_BYTES: u64 = 32 * 1024 * 1024;
const RELEASE_PREFIX: &str =
    "https://github.com/KosmosSG/artcraft-android/releases/tag/filmcraft-v";

pub struct FilmcraftFeatures {
    app: AndroidApp,
    app_dir: Option<PathBuf>,
    registered: HashSet<PathBuf>,
    pending_font: bool,
    pending_updates: bool,
    startup_updates: bool,
    font_status: String,
    update_status: String,
    update_page: Option<String>,
}

impl FilmcraftFeatures {
    // Callers own the Activity lifetime; borrow its native global JNI reference,
    // following the existing ArtCraft SAF/IME bridges.
    fn with_env<T>(
        app: &AndroidApp,
        fun: impl FnOnce(&mut jni::Env<'_>, &JObject<'_>) -> jni::errors::Result<T>,
    ) -> Result<T, String> {
        // SAFETY: AndroidApp owns the VM and global activity for its active lifetime.
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        vm.attach_current_thread(|env| -> jni::errors::Result<T> {
            let raw = app.activity_as_ptr() as jni::sys::jobject;
            // SAFETY: as_cast_raw borrows AndroidApp's global activity reference.
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            match fun(env, &*activity) {
                Ok(value) => Ok(value),
                Err(error) => {
                    let _ = env.exception_clear();
                    Err(error)
                }
            }
        }).map_err(|e| e.to_string())
    }

    fn java_string(app: &AndroidApp, method: &'static str) -> Result<Option<String>, String> {
        Self::with_env(app, |env, activity| {
            let value = match method {
                "fcFeatureFilesDir" => env.call_method(
                    activity, jni_str!("fcFeatureFilesDir"),
                    jni_sig!("()Ljava/lang/String;"), &[],
                )?,
                "fcFeaturePoll" => env.call_method(
                    activity, jni_str!("fcFeaturePoll"),
                    jni_sig!("()Ljava/lang/String;"), &[],
                )?,
                _ => return Ok(None),
            }.l()?;
            if value.is_null() { return Ok(None); }
            let java = JString::cast_local(env, value)?;
            Ok(Some(java.try_to_string(env)?))
        })
    }

    fn java_bool(app: &AndroidApp) -> Result<bool, String> {
        Self::with_env(app, |env, activity| {
            Ok(env.call_method(
                activity, jni_str!("fcStartupUpdatesEnabled"),
                jni_sig!("()Z"), &[],
            )?.z()?)
        })
    }

    fn java_command(&self, command: &str, arg: Option<&str>, toggle: bool)
        -> Result<(), String> {
        Self::with_env(&self.app, |env, activity| {
            match command {
                "import" => { env.call_method(
                    activity, jni_str!("fcRequestFontImport"), jni_sig!("()V"), &[],
                )?; },
                "folder" => { env.call_method(
                    activity, jni_str!("fcRequestSharedFontFolder"), jni_sig!("()V"), &[],
                )?; },
                "refresh" => { env.call_method(
                    activity, jni_str!("fcRefreshSharedFonts"), jni_sig!("()V"), &[],
                )?; },
                "updates" => { env.call_method(
                    activity, jni_str!("fcCheckForUpdates"), jni_sig!("()V"), &[],
                )?; },
                "startup" => { env.call_method(
                    activity, jni_str!("fcSetStartupUpdatesEnabled"), jni_sig!("(Z)V"),
                    &[JValue::Bool(toggle)],
                )?; },
                "open_release" => {
                    let Some(url) = arg else { return Ok(()); };
                    let jurl = JObject::from(env.new_string(url)?);
                    env.call_method(
                        activity, jni_str!("fcOpenUpdatePage"),
                        jni_sig!("(Ljava/lang/String;)V"),
                        &[JValue::Object(&jurl)],
                    )?;
                },
                _ => return Ok(()),
            }
            Ok(())
        })
    }

    pub fn new(app: &AndroidApp) -> Self {
        let app_dir = Self::java_string(app, "fcFeatureFilesDir")
            .ok().flatten().map(PathBuf::from);
        let startup_updates = Self::java_bool(app).unwrap_or(false);
        let mut this = Self {
            app: app.clone(),
            app_dir,
            registered: HashSet::new(),
            pending_font: false,
            pending_updates: false,
            startup_updates,
            font_status: String::new(),
            update_status: String::new(),
            update_page: None,
        };
        // Restore app-private fonts using FilmCraft's live font registry.
        if let Some(dir) = this.app_dir.clone() {
            let (good, bad) = this.load_folder(&dir.join("custom-fonts"));
            if good > 0 || bad > 0 {
                this.font_status = format!("Restored {good} fonts; skipped {bad}");
            }
        }
        // Re-read an SAF-granted shared folder, if selected in a previous session.
        // A missing selection is harmless; it does not request broad storage access.
        let _ = this.java_command("refresh", None, false);
        if this.startup_updates {
            match this.java_command("updates", None, false) {
                Ok(()) => {
                    this.pending_updates = true;
                    this.update_status = "Checking FilmCraft releases…".to_owned();
                }
                Err(e) => this.update_status = format!("Update check unavailable: {e}"),
            }
        }
        this
    }

    fn register_file(&mut self, path: &Path) -> Result<usize, String> {
        let ext_ok = path.extension().and_then(|x| x.to_str()).is_some_and(
            |x| x.eq_ignore_ascii_case("ttf") || x.eq_ignore_ascii_case("otf")
        );
        if !ext_ok { return Err("Unsupported font extension".into()); }
        let metadata = std::fs::metadata(path).map_err(|e| e.to_string())?;
        if !metadata.is_file() || metadata.len() == 0 || metadata.len() > MAX_FONT_BYTES {
            return Err("Font is empty or larger than 32 MiB".into());
        }
        let canonical = path.canonicalize().map_err(|e| e.to_string())?;
        let root = self.app_dir.as_ref().ok_or("App storage unavailable")?
            .canonicalize().map_err(|e| e.to_string())?;
        if !canonical.starts_with(&root) {
            return Err("Font is outside the app's private cache".into());
        }
        if self.registered.contains(&canonical) { return Ok(0); }
        let bytes = std::fs::read(&canonical).map_err(|e| e.to_string())?;
        // add_font_data() is FilmCraft's API; it also updates families() for
        // title/caption style selectors. Do not mutate the upstream font engine.
        let faces = filmcraft_text::fonts::add_font_data(bytes);
        if faces.is_empty() { return Err("Font parser found no supported faces".into()); }
        self.registered.insert(canonical);
        Ok(faces.len())
    }

    fn load_folder(&mut self, folder: &Path) -> (usize, usize) {
        let mut good = 0; let mut bad = 0;
        let Ok(files) = std::fs::read_dir(folder) else { return (0, 0) };
        for (index, file) in files.enumerate() {
            if index >= 256 { break; }
            let Ok(file) = file else { bad += 1; continue; };
            let path = file.path();
            if !path.is_file() { continue; }
            match self.register_file(&path) {
                Ok(n) => good += n,
                Err(e) => { bad += 1; log::warn!("Font {}: {e}", path.display()); }
            }
        }
        (good, bad)
    }

    /// Bridge native FilmCraft menu commands to the existing Java/SAF operations.
    /// The menu runs in the upstream UI crate; this wrapper polls the same egui context.
    fn native_menu_action(&mut self, action: u8) -> String {
        match action {
            1 | 2 | 3 if self.pending_font => {
                self.font_status = "Finish the previous font operation first".into();
            },
            1 => {
                match self.java_command("import", None, false) {
                    Ok(()) => { self.pending_font = true; self.font_status = "Choose a TTF/OTF font…".into(); },
                    Err(e) => self.font_status = format!("Font import unavailable: {e}"),
                }
            },
            2 => {
                match self.java_command("folder", None, false) {
                    Ok(()) => { self.pending_font = true; self.font_status = "Choose shared font folder…".into(); },
                    Err(e) => self.font_status = format!("Shared font folder unavailable: {e}"),
                }
            },
            3 => {
                match self.java_command("refresh", None, false) {
                    Ok(()) => { self.pending_font = true; self.font_status = "Refreshing imported fonts…".into(); },
                    Err(e) => self.font_status = format!("Font refresh unavailable: {e}"),
                }
            },
            4 if self.pending_updates => {
                self.update_status = "Update check is already running".into();
            },
            4 => {
                self.update_page = None;
                match self.java_command("updates", None, false) {
                    Ok(()) => { self.pending_updates = true; self.update_status = "Checking FilmCraft Android releases…".into(); },
                    Err(e) => self.update_status = format!("Update check unavailable: {e}"),
                }
            },
            5 => {
                let enabled = !self.startup_updates;
                match self.java_command("startup", None, enabled) {
                    Ok(()) => {
                        self.startup_updates = enabled;
                        self.update_status = format!("Startup update checks {}", if enabled { "enabled" } else { "disabled" });
                    },
                    Err(e) => self.update_status = format!("Could not save startup update preference: {e}"),
                }
            },
            6 => {
                match self.update_page.clone() {
                    Some(url) if url.starts_with(RELEASE_PREFIX) =>
                        match self.java_command("open_release", Some(&url), false) {
                            Ok(()) => self.update_status = "Opening verified FilmCraft release page…".into(),
                            Err(e) => self.update_status = format!("Could not open release: {e}"),
                        },
                    _ => self.update_status = "No verified release selected; use Check for Updates first".into(),
                }
            },
            7 => {
                let source = option_env!("GITHUB_SHA").unwrap_or("unknown");
                let source = &source[..source.len().min(12)];
                self.update_status = format!(
                    "FilmCraft Android 0.10.0-android.2 | source {source} | disposable test signature"
                );
            },
            _ => return String::new(),
        }
        if action <= 3 { self.font_status.clone() } else { self.update_status.clone() }
    }

    fn native_menu_status(ctx: &egui::Context, status: &str) {
        ctx.data_mut(|data| {
            data.insert_temp(egui::Id::new("filmcraft.android.menu.status"), status.to_owned());
        });
        ctx.request_repaint();
    }

    pub fn poll(&mut self, ctx: &egui::Context) {
        // Consume once; menu invocation may occur after our poll in the UI frame.
        let id = egui::Id::new("filmcraft.android.menu.action");
        let action = ctx.data_mut(|data| {
            let value = data.get_temp::<u8>(id).unwrap_or(0);
            if value != 0 { data.insert_temp(id, 0u8); }
            value
        });
        if action != 0 {
            let status = self.native_menu_action(action);
            if !status.is_empty() { Self::native_menu_status(ctx, &status); }
        }
        for _ in 0..12 {
            let raw = match Self::java_string(&self.app, "fcFeaturePoll") {
                Ok(Some(value)) => value,
                Ok(None) => break,
                Err(error) => {
                    self.pending_updates = false;
                    self.pending_font = false;
                    self.font_status = format!("Android feature bridge unavailable: {error}");
                    break;
                }
            };
            let parsed = serde_json::from_str::<serde_json::Value>(&raw);
            let Ok(v) = parsed else {
                self.font_status = "Android returned malformed feature data".to_owned();
                continue;
            };
            let kind = v["kind"].as_str().unwrap_or("");
            let state = v["status"].as_str().unwrap_or("error");
            let message = v["message"].as_str().unwrap_or("Unknown error");
            match kind {
                "font_import" | "font_folder" => {
                    self.pending_font = false;
                    if state == "ok" {
                        let mut good = 0; let mut bad = 0;
                        if let Some(paths) = v["paths"].as_array() {
                            for path in paths.iter().take(256).filter_map(|x| x.as_str()) {
                                match self.register_file(Path::new(path)) {
                                    Ok(n) => good += n,
                                    Err(error) => {
                                        bad += 1;
                                        log::warn!("Font register failed: {error}");
                                    }
                                }
                            }
                        }
                        self.font_status = format!("{message}. Registered {good} faces; skipped {bad}");
                    } else if state != "cancel" {
                        self.font_status = message.to_owned();
                    }
                },
                "updates" => {
                    self.pending_updates = false;
                    self.update_page = None;
                    let installed = v["installed"].as_str().unwrap_or("unknown");
                    let latest = v["latest"].as_str().unwrap_or("unknown");
                    self.update_status = match state {
                        "available" => format!("FilmCraft {latest} available; installed {installed}"),
                        "current" => format!("Up to date: FilmCraft {installed}"),
                        "none" => "No verified FilmCraft Android public release yet".into(),
                        _ => message.to_owned(),
                    };
                    if state == "available" {
                        self.update_page = v["url"].as_str()
                            .filter(|url| url.starts_with(RELEASE_PREFIX)
                                && !url.contains('?') && !url.contains('#'))
                            .map(ToOwned::to_owned);
                    }
                },
                _ => log::warn!("Unexpected FilmCraft feature event"),
            }
            if kind == "updates" {
                Self::native_menu_status(ctx, &self.update_status);
            } else if kind == "font_import" || kind == "font_folder" {
                Self::native_menu_status(ctx, &self.font_status);
            }
            ctx.request_repaint();
        }
        if self.pending_font || self.pending_updates {
            ctx.request_repaint_after(std::time::Duration::from_millis(250));
        }
    }

    /// A small non-floating Android bar; FilmCraft keeps its native timeline and menus.
    pub fn toolbar(&mut self, ui: &mut egui::Ui) {
        egui::Panel::top("filmcraft_android_feature_bar")
            .resizable(false)
            .show(ui, |ui| {
                ui.horizontal_wrapped(|ui| {
                    ui.label("FilmCraft Android");
                    ui.add_enabled_ui(!self.pending_font, |ui| {
                        if ui.button("Import TTF/OTF").clicked() {
                            match self.java_command("import", None, false) {
                                Ok(()) => { self.pending_font = true; self.font_status = "Choose a font…".into(); },
                                Err(e) => self.font_status = format!("Import unavailable: {e}"),
                            }
                        }
                        if ui.button("Shared font folder").clicked() {
                            match self.java_command("folder", None, false) {
                                Ok(()) => { self.pending_font = true; self.font_status = "Choose your shared ArtCraft-Fonts folder…".into(); },
                                Err(e) => self.font_status = format!("Folder picker unavailable: {e}"),
                            }
                        }
                        if ui.button("Refresh fonts").clicked() {
                            match self.java_command("refresh", None, false) {
                                Ok(()) => { self.pending_font = true; self.font_status = "Refreshing shared fonts…".into(); },
                                Err(e) => self.font_status = format!("Refresh unavailable: {e}"),
                            }
                        }
                    });
                    if ui.add_enabled(!self.pending_updates, egui::Button::new("Check updates")).clicked() {
                        self.update_page = None;
                        match self.java_command("updates", None, false) {
                            Ok(()) => { self.pending_updates = true; self.update_status = "Checking FilmCraft releases…".into(); },
                            Err(e) => self.update_status = format!("Check unavailable: {e}"),
                        }
                    }
                    let mut startup = self.startup_updates;
                    if ui.checkbox(&mut startup, "Check at startup").changed() {
                        match self.java_command("startup", None, startup) {
                            Ok(()) => self.startup_updates = startup,
                            Err(e) => self.update_status = format!("Could not save preference: {e}"),
                        }
                    }
                    if let Some(url) = self.update_page.clone() {
                        if ui.button("Open release").clicked() {
                            if let Err(e) = self.java_command("open_release", Some(&url), false) {
                                self.update_status = format!("Could not open release: {e}");
                            }
                        }
                    }
                });
                if !self.font_status.is_empty() || !self.update_status.is_empty() {
                    ui.horizontal_wrapped(|ui| {
                        if !self.font_status.is_empty() { ui.small(&self.font_status); }
                        if !self.update_status.is_empty() { ui.small(&self.update_status); }
                    });
                }
            });
    }
}
