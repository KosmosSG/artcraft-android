//! Builder-owned Android shell for VectorCraft.
//!
//! Platform file operations use Android's Storage Access Framework (SAF). The Java
//! `VectorCraftActivity` runs the pickers, stages picked documents inside app-private storage and
//! remembers a save destination's URI; the Rust side reads staged paths with the standard file API,
//! writes bytes to them, and copies them back through ContentResolver. The upstream VectorCraft
//! crates remain unchanged.
//!
//! VectorCraft shows its file dialogs off the UI thread through [`Services::start_pick`]: a command
//! (or a dialog's OK) runs as an entry, asking returns no path for now, and when the picker answers
//! the entry runs again with the picked path. The picker is launched through JNI and its answer is
//! delivered into the receiver each frame by [`poll_answers`].
//!
//! ARTCRAFT_VECTORCRAFT_SAF_BRIDGE_V1

use android_activity::AndroidApp;
use jni::{
    JavaVM, jni_sig, jni_str,
    objects::{JObject, JString, JValue},
};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::{Arc, Mutex};
use vectorcraft_engine::{Session, UiRequest};
use vectorcraft_tools::{ToolKey, Mods};
use vectorcraft_ui_egui::picks::PickRequest;
use vectorcraft_ui_egui::{FilePick, Inbox, Services, VectorcraftApp};

// Shared with the generated launchers: brings the device's own system fonts into the egui fallback
// chain and makes them visible to the app's own font scanners (see templates/android/system_fonts.rs).
mod system_fonts;

// Shared with the generated launchers: turns Android's soft keyboard into egui IME events (see
// templates/android/ime_bridge.rs). The `mod ime_bridge;` marker also keeps the vendored
// android-activity, which forwards show/hide to this Activity's imeShow/imeHide, in step.
mod ime_bridge;

// Device-tested MagicPad physical keyboard recovery and guarded Contextual Task Bar Escape.
mod android_modifiers;
use android_modifiers::{AndroidModifiers, apply_android_modifiers, restore_tool_key_text, normalize_type_editor_escape, canvas_hardware_command, consume_canvas_hardware_command, CanvasHardwareCommand};

/// Emitted at startup so the builder can confirm the bridge is present in the packaged `.so`.
const SAF_BRIDGE_MARKER: &str = "ARTCRAFT_VECTORCRAFT_SAF_BRIDGE_V1";

/// Emitted at startup so a device log (and the packaged `.so` strings) can confirm this shell —
/// including the Android modifier-key fix and immersive fullscreen — is the one that is running.
const ANDROID_SHELL_MARKER: &str = "ARTCRAFT_VECTORCRAFT_ANDROID_SHELL_V2_MODIFIERS_FULLSCREEN";

struct AndroidFileBridge {
    app: AndroidApp,
    vm: Arc<JavaVM>,
}

impl AndroidFileBridge {
    fn new(app: AndroidApp) -> Result<Self, String> {
        // AndroidApp owns the live VM pointer for the lifetime of the activity.
        let vm = unsafe { JavaVM::from_raw(app.vm_as_ptr() as *mut _) };
        Ok(Self {
            app,
            vm: Arc::new(vm),
        })
    }

    /// Keep the JavaVM and the AndroidApp cheap to clone into the platform-service closures.
    fn clone_for_services(&self) -> Self {
        Self {
            app: self.app.clone(),
            vm: self.vm.clone(),
        }
    }

    /// Restore native canvas keyboard focus after a completed Type editor Escape.
    fn end_type_editing(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
            env.call_method(&*activity, jni_str!("vcEndTypeEditing"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn request_open(&self, id: u64, multiple: bool, mime: &str) -> Result<(), String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<()> {
                // AndroidApp returns an unowned global ref. Do not delete it when this wrapper drops.
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let mime = env.new_string(mime)?;
                let mime_obj = JObject::from(mime);
                env.call_method(
                    &*activity,
                    jni_str!("vcRequestOpen"),
                    jni_sig!("(JZLjava/lang/String;)V"),
                    &[
                        JValue::Long(id as i64),
                        JValue::Bool(multiple),
                        JValue::Object(&mime_obj),
                    ],
                )?;
                Ok(())
            })
            .map_err(|e| e.to_string())
    }

    fn request_save(&self, id: u64, name: &str, mime: &str) -> Result<(), String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<()> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let name = env.new_string(name)?;
                let name_obj = JObject::from(name);
                let mime = env.new_string(mime)?;
                let mime_obj = JObject::from(mime);
                env.call_method(
                    &*activity,
                    jni_str!("vcRequestSave"),
                    jni_sig!("(JLjava/lang/String;Ljava/lang/String;)V"),
                    &[
                        JValue::Long(id as i64),
                        JValue::Object(&name_obj),
                        JValue::Object(&mime_obj),
                    ],
                )?;
                Ok(())
            })
            .map_err(|e| e.to_string())
    }

    fn poll_result(&self) -> Result<Option<String>, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("vcPollPickerResult"),
                        jni_sig!("()Ljava/lang/String;"),
                        &[],
                    )?
                    .l()?;
                if value.is_null() {
                    return Ok(None);
                }
                let value = JString::cast_local(env, value)?;
                let value: String = value.try_to_string(env)?;
                Ok(Some(value))
            })
            .map_err(|e| e.to_string())
    }

    /// Hand back the private path of one file the system asked this app to open (an
    /// `ACTION_VIEW`/`ACTION_SEND` it is registered for), or `None` when nothing is pending. Returns
    /// an error when the Activity has no intent host; the caller then stops asking.
    fn intent_poll(&self) -> Result<Option<String>, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = match env.call_method(
                    &*activity,
                    jni_str!("intentPoll"),
                    jni_sig!("()Ljava/lang/String;"),
                    &[],
                ) {
                    Ok(value) => value.l()?,
                    Err(error) => {
                        // A missing `intentPoll` leaves a pending NoSuchMethodError on the shared
                        // JNI thread (the picker bridge uses it too); clear it before returning.
                        env.exception_clear();
                        return Err(error);
                    }
                };
                if value.is_null() {
                    return Ok(None);
                }
                let value = JString::cast_local(env, value)?;
                let value: String = value.try_to_string(env)?;
                Ok(Some(value))
            })
            .map_err(|e| e.to_string())
    }


    // Read-only Android SAF font library and official GitHub update checker.
    fn request_font_import(&self, id: u64) -> Result<(), String> {
        self.call_id("vcRequestFontImport", id)
    }

    fn request_font_folder(&self, id: u64, refresh: bool) -> Result<(), String> {
        self.call_id(if refresh { "vcRefreshFontFolder" } else { "vcRequestFontFolder" }, id)
    }

    fn call_id(&self, method: &str, id: u64) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            // JNI signatures are fixed; no dynamically derived method name escapes this match.
            let result = match method {
                "vcRequestFontImport" => env.call_method(&*activity,
                    jni_str!("vcRequestFontImport"), jni_sig!("(J)V"), &[JValue::Long(id as i64)]),
                "vcRefreshFontFolder" => env.call_method(&*activity,
                    jni_str!("vcRefreshFontFolder"), jni_sig!("(J)V"), &[JValue::Long(id as i64)]),
                _ => env.call_method(&*activity,
                    jni_str!("vcRequestFontFolder"), jni_sig!("(J)V"), &[JValue::Long(id as i64)]),
            };
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn check_for_updates(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity,
                jni_str!("vcCheckForUpdates"), jni_sig!("()V"), &[]);
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    // LightCraft-style persistent update channel, stored in Android's private
    // SharedPreferences. JNI failures are surfaced to the About → Updates UI.
    fn get_include_preview_updates(&self) -> Result<bool, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<bool> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcGetIncludePreviewUpdates"),
                jni_sig!("()Z"), &[])?.z()
        }).map_err(|e| e.to_string())
    }

    fn set_include_preview_updates(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcSetIncludePreviewUpdates"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn poll_update_result(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("vcPollUpdateResult"),
                jni_sig!("()Ljava/lang/String;"), &[]);
            if result.is_err() { env.exception_clear(); }
            let value = result?.l()?;
            if value.is_null() { return Ok(None); }
            let value = JString::cast_local(env, value)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn open_update_page(&self, url: &str) -> Result<(), String> {
        const PREFIX: &str =
            "https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v";
        if !url.starts_with(PREFIX) {
            return Err("Not a VectorCraft release link".into());
        }
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let url_obj = JObject::from(env.new_string(url)?);
            let result = env.call_method(&*activity, jni_str!("vcOpenUpdatePage"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&url_obj)]);
            if result.is_err() { env.exception_clear(); }
            result?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn files_dir(&self) -> Result<String, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<String> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("vcFilesDir"),
                        jni_sig!("()Ljava/lang/String;"),
                        &[],
                    )?
                    .l()?;
                let value = JString::cast_local(env, value)?;
                let value: String = value.try_to_string(env)?;
                Ok(value)
            })
            .map_err(|e| e.to_string())
    }

    /// `NONE` for ordinary private paths, `OK` after committing a selected SAF destination, or
    /// `ERROR:<message>` when the Android provider refused the write.
    fn commit_if_mapped(&self, path: &str) -> Result<String, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<String> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let path = env.new_string(path)?;
                let path_obj = JObject::from(path);
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("vcCommitIfMapped"),
                        jni_sig!("(Ljava/lang/String;)Ljava/lang/String;"),
                        &[JValue::Object(&path_obj)],
                    )?
                    .l()?;
                let value = JString::cast_local(env, value)?;
                let value: String = value.try_to_string(env)?;
                Ok(value)
            })
            .map_err(|e| e.to_string())
    }
}

/// The picker requests in flight: their answer receivers, keyed by request id.
#[derive(Default)]
struct PickState {
    next_id: AtomicU64,
    senders: Mutex<HashMap<u64, Sender<Vec<String>>>>,
}

impl PickState {
    fn next_id(&self) -> u64 {
        self.next_id.fetch_add(1, Ordering::Relaxed).wrapping_add(1)
    }

    fn insert(&self, id: u64, sender: Sender<Vec<String>>) {
        self.senders
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .insert(id, sender);
    }

    fn remove(&self, id: u64) -> Option<Sender<Vec<String>>> {
        self.senders
            .lock()
            .unwrap_or_else(|e| e.into_inner())
            .remove(&id)
    }
}


#[derive(Default)]
struct FontUiState {
    pending_import: Option<u64>,
    pending_shared: Option<u64>,
    import_status: String,
    shared_status: String,
}

impl FontUiState {
    fn import(&mut self, picks: &PickState, bridge: &AndroidFileBridge) {
        if self.pending_import.is_some() { return; }
        let id = picks.next_id();
        match bridge.request_font_import(id) {
            Ok(()) => {
                self.pending_import = Some(id);
                self.import_status = "Choose a .ttf or .otf file".into();
            }
            Err(error) => self.import_status = format!("Font picker unavailable: {error}"),
        }
    }

    fn shared(&mut self, picks: &PickState, bridge: &AndroidFileBridge, refresh: bool) {
        if self.pending_shared.is_some() { return; }
        let id = picks.next_id();
        match bridge.request_font_folder(id, refresh) {
            Ok(()) => {
                self.pending_shared = Some(id);
                self.shared_status = if refresh { "Refreshing shared fonts…" }
                    else { "Select ArtCraft-Fonts in Android Files…" }.into();
            }
            Err(error) => self.shared_status = format!("Shared folder unavailable: {error}"),
        }
    }

    /// Returns true only when VectorCraft should rescan its registered Fonts directory.
    fn consume(&mut self, id: u64, value: &serde_json::Value) -> Option<bool> {
        let font_import = self.pending_import == Some(id);
        let font_folder = self.pending_shared == Some(id);
        if !font_import && !font_folder { return None; }
        let success = value.get("status").and_then(serde_json::Value::as_str) == Some("ok");
        let message = value.get("message").and_then(serde_json::Value::as_str)
            .unwrap_or(if success { "Fonts loaded" } else { "Could not load fonts" });
        if font_import {
            self.pending_import = None;
            self.import_status = message.into();
        } else {
            self.pending_shared = None;
            self.shared_status = message.into();
        }
        Some(success)
    }
}

#[derive(Default)]
struct UpdateDialogState {
    checking: bool,
    message: String,
    release_url: Option<String>,
    include_preview: bool,
}

/// A MIME type for an open dialog, from its first file-type filter (every file when it has none).
fn mime_for_filters(pick: &FilePick) -> String {
    pick.filters
        .first()
        .and_then(|(_, exts)| exts.first().copied())
        .map(mime_for_extension)
        .unwrap_or_else(|| "*/*".to_string())
}

fn mime_for_name(name: &str) -> String {
    let ext = Path::new(name)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or_default();
    mime_for_extension(ext)
}

fn mime_for_extension(ext: &str) -> String {
    match ext.to_ascii_lowercase().as_str() {
        "svg" | "svgz" => "image/svg+xml",
        "pdf" => "application/pdf",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "webp" => "image/webp",
        "gif" => "image/gif",
        "tif" | "tiff" => "image/tiff",
        "bmp" => "image/bmp",
        _ => "*/*",
    }
    .to_string()
}

/// Show `request`'s Android picker off the UI thread; the answer arrives on the receiver. `None`
/// when this host can't (a folder picker): the request is then dropped as cancelled.
fn start_pick(
    state: &Arc<PickState>,
    bridge: &AndroidFileBridge,
    request: PickRequest,
) -> Option<Receiver<Vec<String>>> {
    let id = state.next_id();
    let (tx, rx) = mpsc::channel();
    let launch = match request {
        PickRequest::Open(pick) => {
            let mime = mime_for_filters(&pick);
            state.insert(id, tx);
            bridge.request_open(id, false, &mime)
        }
        PickRequest::OpenMany => {
            state.insert(id, tx);
            bridge.request_open(id, true, "*/*")
        }
        PickRequest::Save(pick) => {
            let name = if pick.name.trim().is_empty() {
                "Untitled.svg".to_string()
            } else {
                pick.name.clone()
            };
            let mime = mime_for_name(&name);
            state.insert(id, tx);
            bridge.request_save(id, &name, &mime)
        }
        PickRequest::Folder => return None,
    };
    if let Err(error) = launch {
        state.remove(id);
        log::error!("Could not start the Android file picker: {error}");
        return None;
    }
    Some(rx)
}

/// Each frame: read every picker answer Android queued and send it to the request that asked.
fn poll_answers(state: &Arc<PickState>, bridge: &AndroidFileBridge, ctx: &egui::Context,
    fonts: &mut FontUiState) -> bool {
    let mut rescan = false;
    // Each answer is one short JSON object queued by VectorCraftActivity after picker I/O ends.
    for _ in 0..8 {
        let raw = match bridge.poll_result() {
            Ok(Some(raw)) => raw,
            Ok(None) => break,
            Err(error) => {
                log::error!("Android file picker polling failed: {error}");
                break;
            }
        };
        let value: serde_json::Value = match serde_json::from_str(&raw) {
            Ok(value) => value,
            Err(error) => {
                log::error!("Invalid Android picker result: {error}: {raw}");
                continue;
            }
        };
        let Some(id) = value.get("id").and_then(serde_json::Value::as_u64) else {
            log::error!("Android picker result has no request id: {raw}");
            continue;
        };
        if let Some(changed) = fonts.consume(id, &value) {
            rescan |= changed;
            ctx.request_repaint();
            continue;
        }
        let Some(sender) = state.remove(id) else {
            log::warn!("Ignoring stale Android picker reply {id}");
            continue;
        };
        let status = value
            .get("status")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("error");
        let paths: Vec<String> = match status {
            "cancel" => Vec::new(),
            "ok" => value
                .get("paths")
                .and_then(serde_json::Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(serde_json::Value::as_str)
                .map(str::to_owned)
                .collect(),
            _ => {
                log::error!(
                    "Android file picker failed: {}",
                    value
                        .get("message")
                        .and_then(serde_json::Value::as_str)
                        .unwrap_or("unknown error")
                );
                Vec::new()
            }
        };
        let _ = sender.send(paths);
        ctx.request_repaint();
    }
    rescan
}

/// Write `bytes` to `path`, then copy them to the selected SAF document when `path` is staged.
fn write_mobile(bridge: &AndroidFileBridge, path: &str, bytes: &[u8]) -> Result<(), String> {
    let target = Path::new(path);
    if let Some(parent) = target.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Could not create {}: {e}", parent.display()))?;
    }
    fs::write(target, bytes).map_err(|e| format!("Could not write {}: {e}", target.display()))?;
    match bridge.commit_if_mapped(path)? {
        state if state == "NONE" || state == "OK" => Ok(()),
        state if state.starts_with("ERROR:") => Err(state.trim_start_matches("ERROR:").to_owned()),
        state => Err(format!("Unexpected Android save result: {state}")),
    }
}

/// The app's private storage directory. Android exposes two: the internal one
/// (`/data/user/0/<pkg>/files`), which a file manager or a computer never sees, and the app-specific
/// external one (`/storage/emulated/0/Android/data/<pkg>/files`), which the user can reach over USB
/// or MTP without root. The external directory is preferred so the settings, autosaves and exported
/// documents are actually findable; the internal directory is the fallback for the rare device where
/// external storage is unmounted or unavailable.
fn app_data_dir(app: &AndroidApp) -> Option<std::path::PathBuf> {
    app.external_data_path().or_else(|| app.internal_data_path())
}

/// Where the app keeps its settings, preferences and recent-file list: the app's private files
/// directory plus a `config` subfolder, which survives restarts and updates. The desktop app keeps
/// these in its per-user config folder and the web app in the browser; the Android shell has
/// neither, so it writes them here.
fn persist_dir(app: &AndroidApp) -> Option<std::path::PathBuf> {
    app_data_dir(app).map(|base| base.join("config"))
}

/// Point the platform path helpers at app-private storage before the app reads them, so anything
/// the app writes itself (autosave, recovery copies, caches) also lands there.
#[allow(unused_unsafe)]
fn install_persist_env(app: &AndroidApp) {
    let Some(base) = app_data_dir(app) else { return };
    let config = base.join("config");
    let cache = base.join("cache");
    let home = base.join("home");
    let _ = fs::create_dir_all(config.join(".config"));
    let _ = fs::create_dir_all(&cache);
    let _ = fs::create_dir_all(&home);
    // SAFETY: `android_main` runs before the app starts any worker thread, so no other thread is
    // reading the environment here.
    unsafe {
        std::env::set_var("XDG_CONFIG_HOME", &config);
        std::env::set_var("XDG_DATA_HOME", &base);
        std::env::set_var("XDG_CACHE_HOME", &cache);
        std::env::set_var("HOME", &home);
    }
    log::info!("settings directory: {}", config.display());
}

fn persist_read(dir: &Path, name: &str) -> Option<Vec<u8>> {
    fs::read(dir.join(name)).ok()
}

/// Write `bytes` to `dir/name` through a temporary file renamed over the old one, so a crash leaves
/// the old file or the new one whole, never a truncated one.
fn persist_write(dir: &Path, name: &str, bytes: &[u8]) {
    if let Err(error) = fs::create_dir_all(dir) {
        log::warn!("settings: {}: {error}", dir.display());
        return;
    }
    let path = dir.join(name);
    let temporary = path.with_extension("tmp");
    let written = fs::write(&temporary, bytes).and_then(|()| fs::rename(&temporary, &path));
    if let Err(error) = written {
        log::warn!("settings: {}: {error}", path.display());
    }
}

/// Read a saved `ui.json` leniently: a docking layout or hidden-panel entry this version cannot
/// read is dropped instead of discarding every setting (as the desktop app does).
fn decode_saved_prefs(bytes: &[u8]) -> Option<vectorcraft_ui_egui::UiState> {
    use serde_json::{Map, Value, json};

    fn recover(object: &mut Map<String, Value>, hidden_key: &str) {
        if let Some(layout) = object.get("docking")
            && serde_json::from_value::<vectorcraft_ui_egui::UiState>(json!({"docking": layout})).is_err()
        {
            object.remove("docking");
        }
        if let Some(hidden) = object.get_mut(hidden_key) {
            if let Value::Object(entries) = hidden {
                entries.retain(|panel, location| {
                    serde_json::from_value::<vectorcraft_ui_egui::UiState>(json!({"docking_hidden": {panel: location}})).is_ok()
                });
            } else {
                object.remove(hidden_key);
            }
        }
    }

    let mut value: Value = serde_json::from_slice(bytes).ok()?;
    let object = value.as_object_mut()?;
    recover(object, "docking_hidden");
    if let Some(Value::Array(workspaces)) = object.get_mut("custom_workspaces") {
        for workspace in workspaces {
            if let Some(object) = workspace.as_object_mut() {
                recover(object, "dockingHidden");
            }
        }
    }
    serde_json::from_value(value).ok()
}

/// Load the saved UI state and engine preferences, as the desktop app does at startup.
fn persist_load(app: &mut VectorcraftApp, dir: &Path) {
    if let Some(bytes) = persist_read(dir, "ui.json")
        && let Some(ui) = decode_saved_prefs(&bytes)
    {
        app.ui = ui.sanitized();
    }
    vectorcraft_ui_egui::prefs_dialog::restore(app);
}

/// Save the UI state and engine preferences, as the desktop app does on exit.
fn persist_save(app: &mut VectorcraftApp, dir: &Path) {
    let mut ui = app.ui.clone();
    ui.engine_prefs = app.session.prefs.to_json();
    if let Ok(bytes) = serde_json::to_vec_pretty(&ui) {
        persist_write(dir, "ui.json", &bytes);
    }
}

fn services(bridge: AndroidFileBridge, state: Arc<PickState>, inbox: Inbox) -> Services {
    let write_bridge = bridge.clone_for_services();
    let pick_bridge = bridge.clone_for_services();
    let pick_state = state.clone();
    Services {
        // Files the system asked us to open (ACTION_VIEW/ACTION_SEND) are queued here and drained
        // by the app's own per-frame inbox, exactly like a document chosen in the picker.
        inbox: Some(inbox),
        // A staged document is an ordinary file in app-private storage.
        read: Some(Box::new(|path: &str| {
            fs::read(path).map_err(|e| format!("Could not read {path}: {e}"))
        })),
        write: Some(Box::new(move |path: &str, bytes: &[u8]| {
            write_mobile(&write_bridge, path, bytes)
        })),
        // Shown off the UI thread, so `ask` never calls these; they make the dialogs count as
        // available (`picks::can`).
        pick_open: Some(Box::new(|_pick: &FilePick| None)),
        pick_save: Some(Box::new(|_pick: &FilePick| None)),
        pick_open_multi: Some(Box::new(Vec::new)),
        pick_folder: Some(Box::new(|| None)),
        start_pick: Some(Box::new(move |request: PickRequest| {
            start_pick(&pick_state, &pick_bridge, request)
        })),
        ..Services::default()
    }
}

struct VectorCraftAndroidApp {
    inner: VectorcraftApp,
    bridge: AndroidFileBridge,
    picks: Arc<PickState>,
    fonts: FontUiState,
    font_feedback_open: bool,
    android_tools_open: bool,
    touch_dock: bool,
    startup_updates: bool,
    updates: UpdateDialogState,
    ime: ime_bridge::ime::ImeBridge,
    modifiers: AndroidModifiers,
    persist: Option<std::path::PathBuf>,
    persist_last: Option<std::time::Instant>,
    // Files the system asked us to open are staged by the Activity; this is the shared queue the
    // app's own inbox drains. `intent_warmup` skips the first couple of frames so the app has
    // finished its own start-up, and goes negative (stop polling) if the host has no intent bridge.
    intent_inbox: Inbox,
    intent_warmup: i64,
    // Staged working copies under media/ the app still refers to (see `staged_prune_tick`), and
    // when the one-time orphan sweep of the directory is due.
    staged_seen: Vec<String>,
    staged_sweep_at: Option<std::time::Instant>,
}

/// Read the files the system asked this app to open (an `ACTION_VIEW`/`ACTION_SEND` it is registered
/// for) into the app's import inbox, exactly like a document chosen in the picker. Each staged path
/// is read once; a launcher without the intent host stops the poll after one error.
fn drain_incoming(bridge: &AndroidFileBridge, inbox: &Inbox, warmup: &mut i64) {
    if *warmup > 0 {
        *warmup -= 1;
        return;
    }
    if *warmup < 0 {
        return;
    }
    for _ in 0..16 {
        match bridge.intent_poll() {
            Ok(Some(path)) => match fs::read(&path) {
                Ok(bytes) => {
                    let name = Path::new(&path)
                        .file_name()
                        .map(|name| name.to_string_lossy().into_owned())
                        .unwrap_or_else(|| "imported-file".to_string());
                    log::info!("Opening the file the system handed the app: {path}");
                    inbox.lock().unwrap_or_else(|e| e.into_inner()).push((name, bytes));
                }
                Err(error) => log::error!("Could not read the incoming file {path}: {error}"),
            },
            Ok(None) => break,
            Err(error) => {
                log::info!("Launcher does not report incoming files: {error}");
                *warmup = -1;
                break;
            }
        }
    }
}

impl VectorCraftAndroidApp {
    /// The staged copy of a document, if `path` names one: a *direct* child of the app's own
    /// `media/` directory (see VectorCraftActivity.newStageFile). Anything else on the device is
    /// never touched.
    fn staged_media_file(&self, path: &str) -> Option<PathBuf> {
        let files = self.bridge.files_dir().ok()?;
        let media = Path::new(&files).join("media");
        let file = PathBuf::from(path);
        (file.parent() == Some(media.as_path())).then_some(file)
    }

    /// Delete every staged copy under `media/` that neither the recent list nor an open document
    /// refers to, sparing files written in the last minute (a document may be mid-import). This
    /// clears out copies orphaned before this pruning existed, or by an app killed mid-session.
    fn staged_sweep_orphans(bridge: &AndroidFileBridge, recent: &[String], open: &[String]) {
        let Ok(files) = bridge.files_dir() else { return };
        let media = Path::new(&files).join("media");
        let Ok(entries) = fs::read_dir(&media) else { return };
        for entry in entries.flatten() {
            let path = entry.path();
            if recent.iter().any(|keep| Path::new(keep) == path.as_path())
                || open.iter().any(|keep| Path::new(keep) == path.as_path())
            {
                continue;
            }
            let Ok(meta) = entry.metadata() else { continue };
            if !meta.is_file() {
                continue;
            }
            let fresh = meta
                .modified()
                .ok()
                .and_then(|at| at.elapsed().ok())
                .is_some_and(|age| age < std::time::Duration::from_secs(60));
            if fresh {
                continue;
            }
            let name = path.to_string_lossy().into_owned();
            match fs::remove_file(&path) {
                Ok(()) => log::info!("deleted an orphaned staged copy: {name}"),
                Err(error) => log::warn!("could not delete the staged copy {name}: {error}"),
            }
        }
    }

    /// When an entry leaves the recent-files list (the list is cleared, an entry is removed with
    /// its ×, or it ages out of the capped list) and no open document is showing that file, its
    /// staged copy under `media/` is deleted: the document's original still lives at its SAF
    /// location. The `uri:` mapping in SharedPreferences is deliberately kept, so re-opening the
    /// same document reuses the same path and a later save still reaches the original. A delayed
    /// sweep of the whole directory clears out copies this diff never saw (an older session, or a
    /// crash); it runs once, half a minute after start, to let session restore finish first.
    fn staged_prune_tick(&mut self) {
        let current: Vec<String> = self.inner.ui.recent_files.clone();
        let open: Vec<String> = self
            .inner
            .session
            .documents()
            .iter()
            .filter_map(|doc| doc.path.clone())
            .collect::<Vec<_>>();
        for stale in self
            .staged_seen
            .iter()
            .filter(|path| !current.contains(*path) && !open.contains(*path))
        {
            let Some(file) = self.staged_media_file(stale) else { continue };
            match fs::remove_file(&file) {
                Ok(()) => log::info!("deleted the staged copy of a recent file the app let go: {stale}"),
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                Err(error) => log::warn!("could not delete the staged copy {stale}: {error}"),
            }
        }
        if self.staged_sweep_at.is_some_and(|at| std::time::Instant::now() >= at) {
            self.staged_sweep_at = None;
            Self::staged_sweep_orphans(&self.bridge, &current, &open);
        }
        self.staged_seen = current;
    }

    /// Save settings, preferences and the recent-files list, at most every two seconds. Android
    /// can kill a backgrounded app without a clean exit, so waiting for `on_exit` alone would lose
    /// whatever changed since the last write.
    fn persist_tick(&mut self) {
        let Some(dir) = self.persist.clone() else { return };
        let now = std::time::Instant::now();
        if self.persist_last.is_some_and(|last| now.duration_since(last) < std::time::Duration::from_secs(2)) {
            return;
        }
        self.persist_last = Some(now);
        persist_save(&mut self.inner, &dir);
    }

    /// Save now: the window lost focus (the app is being backgrounded) or it is exiting.
    fn persist_now(&mut self) {
        if let Some(dir) = self.persist.clone() {
            persist_save(&mut self.inner, &dir);
        }
    }
}

impl eframe::App for VectorCraftAndroidApp {
    fn logic(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Deliver picker answers before the app's own logic runs, so `picks::poll` resumes the
        // entry that asked in this same frame.
        if poll_answers(&self.picks, &self.bridge, ctx, &mut self.fonts) {
            // VectorCraft's built-in rescan refreshes available text faces and redraws type.
            if let Err(error) = self.inner.run("text.rescanFonts", serde_json::json!({})) {
                log::warn!("Android font rescan failed: {error}");
                self.fonts.shared_status = format!("Fonts copied, but rescan failed: {error}");
            }
        }
        if self.updates.checking {
            match self.bridge.poll_update_result() {
                Ok(Some(raw)) => {
                    self.updates.checking = false;
                    match serde_json::from_str::<serde_json::Value>(&raw) {
                        Ok(result) => {
                            self.updates.release_url = result.get("url")
                                .and_then(serde_json::Value::as_str)
                                .filter(|url| url.starts_with(
                                    "https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v"))
                                .map(str::to_owned);
                            let installed = result.get("installed_version")
                                .and_then(serde_json::Value::as_str).unwrap_or("unknown");
                            let latest = result.get("latest_version")
                                .and_then(serde_json::Value::as_str).unwrap_or("unknown");
                            self.updates.message = match result.get("state")
                                .and_then(serde_json::Value::as_str) {
                                Some("update_available") => format!(
                                    "Update available: {latest} (installed: {installed})"),
                                Some("up_to_date") => format!(
                                    "You're up to date (installed: {installed}; latest: {latest})."),
                                Some("no_release") => "No published VectorCraft Android APK yet.".into(),
                                _ => format!("Update check failed: {}",
                                    result.get("message").and_then(serde_json::Value::as_str)
                                        .unwrap_or("Unknown response")),
                            };
                        }
                        Err(error) => self.updates.message = format!("Invalid update result: {error}"),
                    }
                    if self.updates.release_url.is_some() && self.updates.message.starts_with("Update available:") {
                        self.updates.open = true;
                    }
                    ctx.request_repaint();
                }
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(250)),
                Err(error) => {
                    self.updates.checking = false;
                    self.updates.message = format!("Update checker unavailable: {error}");
                }
            }
        }
        // Then deliver any file the system asked us to open, through the same inbox.
        drain_incoming(&self.bridge, &self.intent_inbox, &mut self.intent_warmup);
        self.staged_prune_tick();
        self.inner.logic(ctx);
        self.persist_tick();
    }

    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        self.ime.poll(raw);
        apply_android_modifiers(&mut self.modifiers, raw);
        // Upstream v0.14 Type editing claims Escape and returns a SwitchTool
        // request. Routing that request directly avoids stale Android IME focus
        // or an egui focus transition swallowing the physical key.
        let editing = self.inner.session.tool_wants_text();
        let field_focused = ctx.text_edit_focused();
        let composing = self.inner.session.tool_composing();
        let modal = self.inner.ui.dialog.is_some() || self.inner.ui.palette_open;
        let selection_idle = matches!(self.inner.session.tool_id(), "selection" | "directSelection")
            && !self.inner.session.tool_busy();
        let context_bar_with_selection = self.inner.ui.task_bar && selection_idle &&
            self.inner.session.active().is_some_and(|d| d.selection.has_objects_or_guides());
        if let Some(command) = canvas_hardware_command(
            raw, editing, field_focused, composing, modal, context_bar_with_selection,
        ) {
            let mut handled = false;
            match command {
                CanvasHardwareCommand::ExitType => {
                    let view = self.inner.view_info();
                    match self.inner.session.tool_key(ToolKey::Escape, Mods::default(), view) {
                        Ok(requests) => {
                            for request in requests {
                                if let UiRequest::SwitchTool(tool) = request {
                                    self.inner.select_tool(&tool);
                                    handled = true;
                                }
                            }
                        }
                        Err(error) => log::warn!("Type editor Escape failed: {error}"),
                    }
                    if handled {
                        if let Err(error) = self.bridge.end_type_editing() {
                            log::warn!("Android keyboard focus handoff failed: {error}");
                        }
                    }
                }
                CanvasHardwareCommand::DismissContextBar => {
                    // Second Escape uses the existing Hide Bar state; it does
                    // not change the user's keyboard shortcut assignments.
                    self.inner.ui.task_bar = false;
                    ctx.memory_mut(|memory| {
                        if let Some(id) = memory.focused() { memory.surrender_focus(id); }
                    });
                    handled = true;
                }
                CanvasHardwareCommand::Selection
                | CanvasHardwareCommand::Type
                | CanvasHardwareCommand::Pen => {
                    if self.inner.session.active().is_some() {
                        let tool = match command {
                            CanvasHardwareCommand::Selection => "selection",
                            CanvasHardwareCommand::Type => "type",
                            CanvasHardwareCommand::Pen => "pen",
                            CanvasHardwareCommand::ExitType
                            | CanvasHardwareCommand::DismissContextBar => unreachable!(),
                        };
                        self.inner.select_tool(tool);
                        handled = true;
                    }
                }
            }
            if handled { consume_canvas_hardware_command(raw, command); }
        }
        // Leave unrelated Escape, punctuation, modified shortcuts and all
        // IME composition/commit events to the unmodified upstream dispatcher.
        normalize_type_editor_escape(raw, self.inner.session.tool_wants_text());
        let allow_letters = !ctx.text_edit_focused() && !self.inner.session.tool_wants_text();
        restore_tool_key_text(raw, allow_letters);
        if raw.events.iter().any(|event| matches!(event, egui::Event::WindowFocused(false))) {
            self.persist_now();
        }
        self.inner.raw_input_hook(raw);
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        system_fonts::install_system_fonts(ui.ctx());
        vectorcraft_ui_egui::menus::set_android_preferences(self.touch_dock, self.startup_updates);

        // PhotoCraft-style dock: an actual bottom panel reserves editor space instead
        // of floating over canvas handles or intercepting drawing gestures.
        let mut pad_command: Option<&'static str> = None;
        let mut hide_pad = false;
        if self.touch_dock {
            let editing_text = ui.ctx().text_edit_focused();
            let has_doc = self.inner.session.active().is_some();
            egui::Panel::bottom("vectorcraft.android.touch_shortcut_pad")
                .resizable(false)
                .default_size(56.0)
                .show(ui, |ui| {
                    egui::ScrollArea::horizontal()
                        .id_salt("vectorcraft.android.touch_shortcut_pad.scroll")
                        .show(ui, |ui| {
                            ui.horizontal(|ui| {
                                for (label, command, needs_document) in [
                                    ("Undo", "edit.undo", true),
                                    ("Redo", "edit.redo", true),
                                    ("Fit", "view.fitArtboard", true),
                                    ("100%", "view.actualSize", true),
                                    ("Shortcuts", "edit.keyboardShortcuts", false),
                                ] {
                                    let enabled = !editing_text && (!needs_document || has_doc);
                                    if ui.add_enabled(enabled,
                                        egui::Button::new(label)
                                            .min_size(egui::vec2(64.0, 44.0)))
                                        .clicked() {
                                        pad_command = Some(command);
                                    }
                                }
                                if ui.add(egui::Button::new("Hide pad")
                                    .min_size(egui::vec2(74.0, 44.0))).clicked() {
                                    hide_pad = true;
                                }
                            });
                        });
                });
        }
        // LightCraft's About → Updates tab reads these native states directly.
        // Publish BEFORE the upstream ui() call, which draws About VectorCraft.
        let status = if self.updates.message.is_empty() {
            "Select Check for Updates to query GitHub Releases.".to_owned()
        } else {
            self.updates.message.clone()
        };
        ui.ctx().data_mut(|d| {
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_status"), status);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.installed_version"),
                env!("CARGO_PKG_VERSION").to_owned());
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_checking"), self.updates.checking);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.include_preview"), self.updates.include_preview);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.startup_enabled"), self.startup_updates);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.release_page"),
                self.updates.release_url.clone().unwrap_or_default());
        });
        // The editor uses space left after the bottom shortcut dock; About is
        // the genuine upstream dialog, not a separate floating update overlay.
        self.inner.ui(ui);

        // Small Android-only entry point: no upstream desktop preferences are changed.
        let ctx = ui.ctx();
        let mut import = false;
        let mut select_shared = false;
        let mut refresh_shared = false;
        let mut check_updates = false;
        let (tab_check, tab_startup_changed, tab_startup_desired,
             tab_preview_changed, tab_preview_desired, tab_open_release) =
             ctx.data_mut(|d| {
                // Avoid a stale repeated request on every repaint.
                let check = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.check_updates_requested")).unwrap_or(false);
                let startup_changed = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.startup_changed")).unwrap_or(false);
                let startup = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.startup_desired")).unwrap_or(false);
                let preview_changed = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.preview_changed")).unwrap_or(false);
                let preview = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.preview_desired")).unwrap_or(false);
                let open = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.open_release_requested")).unwrap_or(false);
                for key in ["artcraft.vectorcraft.check_updates_requested",
                            "artcraft.vectorcraft.startup_changed",
                            "artcraft.vectorcraft.preview_changed",
                            "artcraft.vectorcraft.open_release_requested"] {
                    d.insert_temp(egui::Id::new(key), false);
                }
                (check, startup_changed, startup, preview_changed, preview, open)
             });
        let mut customize_shortcuts = false;
        let mut dock_undo = false;
        let mut dock_redo = false;
        let previous_touch_dock = self.touch_dock;
        let previous_startup_updates = self.startup_updates;
        // Genuine upstream Type, Help, and Window menu clicks are passed back to the
        // Android host; no desktop menu commands or user shortcut assignments change.
        let menu = vectorcraft_ui_egui::menus::take_android_menu_bits();
        if tab_check { check_updates = true; }
        if tab_startup_changed { self.startup_updates = tab_startup_desired; }
        if tab_preview_changed && tab_preview_desired != self.updates.include_preview {
            match self.bridge.set_include_preview_updates(tab_preview_desired) {
                Ok(()) => {
                    self.updates.include_preview = tab_preview_desired;
                    self.updates.message =
                        "Update channel saved. Select Check for Updates to refresh.".into();
                    self.updates.release_url = None;
                }
                Err(error) => self.updates.message =
                    format!("Could not save update channel: {error}"),
            }
        }
        if tab_open_release {
            if let Some(url) = self.updates.release_url.as_deref() {
                if let Err(error) = self.bridge.open_update_page(url) {
                    self.updates.message = format!("Could not open GitHub release: {error}");
                }
            }
        }
        if menu & 1 != 0 { import = true; }
        if menu & 2 != 0 { select_shared = true; }
        if menu & 4 != 0 { refresh_shared = true; }
        if menu & 8 != 0 { check_updates = true; }
        if menu & 16 != 0 { self.startup_updates = !self.startup_updates; }
        if menu & 32 != 0 { self.touch_dock = !self.touch_dock; }
        if menu & 64 != 0 { self.android_tools_open = true; }
        if hide_pad { self.touch_dock = false; }
        // No persistent floating Android Tools palette. Help exposes read-only
        // graphics and font-import status on demand without covering the canvas.
        if self.android_tools_open {
            let gpu_details = match _frame.wgpu_render_state() {
                Some(state) => {
                    let info = state.adapter.get_info();
                    format!("UI adapter: {}\nBackend: {:?}\nDevice type: {:?}\nDriver: {} {}\nMaximum 2D texture: {} px",
                        info.name, info.backend, info.device_type,
                        info.driver, info.driver_info,
                        state.device.limits().max_texture_dimension_2d)
                }
                None => "GPU adapter/backend unavailable from eframe on this device.".into(),
            };
            egui::Window::new("VectorCraft Graphics Diagnostics")
                .open(&mut self.android_tools_open)
                .default_width(340.0)
                .show(ctx, |ui| {
                    ui.label("Read-only Android graphics information");
                    ui.monospace(gpu_details);
                    ui.separator();
                    ui.label("Font import status");
                    ui.label(&self.fonts.import_status);
                    ui.label(&self.fonts.shared_status);
                });
        }
        if self.startup_updates != previous_startup_updates {
            if let Some(dir) = self.persist.as_ref() {
                persist_write(dir, "startup_updates.enabled", if self.startup_updates { b"1" } else { b"0" });
            }
        }
        if self.touch_dock != previous_touch_dock {
            if let Some(dir) = self.persist.as_ref() {
                if let Err(error) = fs::write(dir.join("touch_dock.enabled"),
                    if self.touch_dock { "1" } else { "0" }) {
                    log::warn!("Could not save shortcut dock preference: {error}");
                }
            }
        }
        if let Some(command) = pad_command {
            if let Err(error) = self.inner.run(command, serde_json::json!({})) {
                log::warn!("VectorCraft Touch Shortcut Pad {command} failed: {error}");
            }
            ctx.request_repaint();
        }
        for (pressed, command) in [(dock_undo, "edit.undo"),
                                   (dock_redo, "edit.redo"),
                                   (customize_shortcuts, "edit.keyboardShortcuts")] {
            if pressed {
                if let Err(error) = self.inner.run(command, serde_json::json!({})) {
                    log::warn!("VectorCraft Android shortcut {command} failed: {error}");
                }
                ctx.request_repaint();
            }
        }
        // An actual feedback window remains visible after SAF returns, including
        // Cancel, duplicate font and I/O failure. Previously these statuses
        // existed but were hidden inside Graphics Diagnostics.
        if import {
            self.font_feedback_open = true;
            self.fonts.import(&self.picks, &self.bridge);
        }
        if select_shared {
            self.font_feedback_open = true;
            self.fonts.shared(&self.picks, &self.bridge, false);
        }
        if refresh_shared {
            self.font_feedback_open = true;
            self.fonts.shared(&self.picks, &self.bridge, true);
        }
        if self.font_feedback_open {
            let mut open = self.font_feedback_open;
            let mut close_button = false;
            egui::Window::new("VectorCraft Fonts")
                .id(egui::Id::new("vectorcraft.android.font_feedback"))
                .collapsible(false)
                .resizable(false)
                .default_width(425.0)
                .order(egui::Order::Foreground)
                .open(&mut open)
                .show(ctx, |ui| {
                    ui.heading("Font Import");
                    ui.separator();
                    if self.fonts.pending_import.is_some() {
                        ui.horizontal(|ui| {
                            ui.spinner();
                            ui.label("Waiting for font selection / import…");
                        });
                    }
                    if !self.fonts.import_status.is_empty() {
                        ui.label(&self.fonts.import_status);
                    }
                    if self.fonts.pending_shared.is_some() {
                        ui.horizontal(|ui| {
                            ui.spinner();
                            ui.label("Loading shared font folder…");
                        });
                    }
                    if !self.fonts.shared_status.is_empty() {
                        ui.label(&self.fonts.shared_status);
                    }
                    ui.add_space(6.0);
                    ui.small("TTF / OTF fonts stay inside VectorCraft's private Fonts folder.");
                    ui.separator();
                    if ui.button("Close").clicked() { close_button = true; }
                });
            self.font_feedback_open = open && !close_button;
        }
        if check_updates {
            // The native About dialog owns the Updates tab, just like
            // LightCraft. In particular, no bottom panel is drawn after the
            // central editor (which made the old status nearly invisible).
            self.inner.ui.about = true;
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("about_tab"), 3u8));
            if !self.updates.checking {
                self.updates.release_url = None;
                self.updates.message = "Checking official VectorCraft GitHub Releases…".into();
                match self.bridge.check_for_updates() {
                    Ok(()) => self.updates.checking = true,
                    Err(error) => self.updates.message =
                        format!("Could not check releases: {error}"),
                }
            }
            ctx.request_repaint();
        }
    }

    fn on_exit(&mut self) {
        self.persist_now();
    }
}

#[cfg(target_os = "android")]
#[unsafe(no_mangle)]
fn android_main(android_app: AndroidApp) {
    log::info!("{SAF_BRIDGE_MARKER} ready; {ANDROID_SHELL_MARKER}; {}", ime_bridge::ime::IME_MARKER);
    install_persist_env(&android_app);
    system_fonts::install_font_env(&android_app);
    let bridge = match AndroidFileBridge::new(android_app.clone()) {
        Ok(bridge) => bridge,
        Err(error) => {
            log::error!("VectorCraft Android startup failed: {error}");
            return;
        }
    };
    if let Ok(dir) = bridge.files_dir() {
        log::info!("VectorCraft app-private storage: {dir}");
        let fonts = PathBuf::from(dir).join("Fonts");
        if let Err(error) = fs::create_dir_all(&fonts) {
            log::warn!("Could not create persistent VectorCraft Fonts folder: {error}");
        }
        // Must run before VectorcraftApp::new catalogs installed fonts.
        vectorcraft_text::set_app_font_dir(fonts);
    }
    let picks = Arc::new(PickState::default());
    let mut initial_fonts = FontUiState::default();
    // Restore a previously authorized shared library on startup; missing access is nonfatal.
    initial_fonts.shared(&picks, &bridge, true);
    let intent_inbox: Inbox = Arc::new(Mutex::new(Vec::new()));
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("VectorCraft")
            .with_drag_and_drop(true),
        android_app: Some(android_app),
        ..Default::default()
    };
    let app_bridge = bridge.clone_for_services();
    let app_picks = picks.clone();
    let app_intent_inbox = intent_inbox.clone();
    let result = eframe::run_native(
        "VectorCraft",
        options,
        Box::new(move |_cc| {
            let mut app = VectorcraftApp::new(
                Session::new(),
                services(app_bridge.clone_for_services(), app_picks.clone(), app_intent_inbox.clone()),
            );
            let persist = persist_dir(&app_bridge.app);
            if let Some(dir) = &persist {
                persist_load(&mut app, dir);
            }
            let touch_dock = persist.as_ref()
                .and_then(|dir| fs::read_to_string(dir.join("touch_dock.enabled")).ok())
                .is_some_and(|value| value.trim() == "1");
            let startup_updates = persist.as_ref()
                .and_then(|dir| fs::read_to_string(dir.join("startup_updates.enabled")).ok())
                .is_some_and(|value| value.trim() == "1");
            Ok(Box::new(VectorCraftAndroidApp {
                inner: app,
                bridge: app_bridge.clone_for_services(),
                picks: app_picks.clone(),
                fonts: std::mem::take(&mut initial_fonts),
                font_feedback_open: false,
                android_tools_open: false,
                touch_dock,
                startup_updates,
                updates: {
                    let mut state = UpdateDialogState::default();
                    // Like LightCraft, preview channel is a persistent Android
                    // preference; do not silently change it during an update.
                    state.include_preview =
                        app_bridge.get_include_preview_updates().unwrap_or(true);
                    state.message = "Select Check for Updates to query GitHub Releases.".into();
                    // Nonblocking startup check remains opt-in.
                    if startup_updates && app_bridge.check_for_updates().is_ok() {
                        state.checking = true;
                        state.message = "Checking for VectorCraft updates…".into();
                    }
                    state
                },
                ime: ime_bridge::ime::ImeBridge::new(&app_bridge.app),
                modifiers: AndroidModifiers::default(),
                persist,
                persist_last: None,
                intent_inbox: app_intent_inbox.clone(),
                intent_warmup: 2,
                staged_seen: Vec::new(),
                staged_sweep_at: Some(std::time::Instant::now() + std::time::Duration::from_secs(30)),
            }))
        }),
    );
    if let Err(error) = result {
        log::error!("VectorCraft Android exited with an error: {error}");
    }
}
