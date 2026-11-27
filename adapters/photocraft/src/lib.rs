//! Builder-owned Android shell for PhotoCraft.
//! Platform file operations use Android's Storage Access Framework (SAF). Selected documents
//! are staged inside app-private storage, with a persistent URI mapping used to write saved bytes
//! back through ContentResolver. The upstream PhotoCraft crates remain unchanged.
//! ARTCRAFT_PHOTOCRAFT_SAF_JNI022_FIX_V1

use android_activity::AndroidApp;
use craft::host::{FileError, Files, PendingPick, PickId, PickKind, PickRequest, Picked, WriteIntent};
use jni::{
    JavaVM, jni_sig, jni_str,
    objects::{JObject, JString, JValue},
};
use photocraft_doc::Document;
use photocraft_engine::Session;
use photocraft_ui_egui::{Inbox, PhotocraftApp, Services};
use std::collections::{HashMap, HashSet, VecDeque};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

// Shared with the generated launchers: brings the device's own system fonts into the egui fallback
// chain and makes them visible to the app's own font scanners (see templates/android/system_fonts.rs).
mod system_fonts;

// Shared with the generated launchers: turns Android's soft keyboard into egui IME events (see
// templates/android/ime_bridge.rs). The `mod ime_bridge;` marker also keeps the vendored
// android-activity, which forwards show/hide to this Activity's imeShow/imeHide, in step.
mod ime_bridge;

// Preview UI and tool declarations live only in the Android adapter.
mod ai_tools;
mod ai_models;
mod ai_menu;
mod ai_u2netp_transport;
mod ai_background_job;
mod ai_output_validation;
mod ai_background_editor;

/// Emitted at startup so a device log (and the packaged `.so` strings) can confirm this shell —
/// including the Android modifier-key fix and immersive fullscreen — is the one that is running.
const ANDROID_SHELL_MARKER: &str = "ARTCRAFT_PHOTOCRAFT_ANDROID_SHELL_V2_MODIFIERS_FULLSCREEN";

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

    fn request_open(&self, id: u64, multiple: bool) -> Result<(), String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<()> {
                // AndroidApp returns an unowned global ref. Do not delete it when this wrapper drops.
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                env.call_method(
                    &*activity,
                    jni_str!("pcRequestOpen"),
                    jni_sig!("(JZ)V"),
                    &[JValue::Long(id as i64), JValue::Bool(multiple)],
                )?;
                Ok(())
            })
            .map_err(|e| e.to_string())
    }

    fn request_save(&self, id: u64, name: &str) -> Result<(), String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<()> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let name = env.new_string(name)?;
                let name_obj = JObject::from(name);
                env.call_method(
                    &*activity,
                    jni_str!("pcRequestSave"),
                    jni_sig!("(JLjava/lang/String;)V"),
                    &[JValue::Long(id as i64), JValue::Object(&name_obj)],
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
                        jni_str!("pcPollPickerResult"),
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

    fn files_dir(&self) -> Result<PathBuf, String> {
        self.vm
            .attach_current_thread(|env| -> jni::errors::Result<PathBuf> {
                let activity_raw = self.app.activity_as_ptr() as jni::sys::jobject;
                // SAFETY: AndroidApp retains this global Activity reference; as_cast_raw borrows it
                // without taking ownership or attempting to delete the reference.
                let activity = unsafe { env.as_cast_raw::<JObject>(&activity_raw)? };
                let value = env
                    .call_method(
                        &*activity,
                        jni_str!("pcFilesDir"),
                        jni_sig!("()Ljava/lang/String;"),
                        &[],
                    )?
                    .l()?;
                let value = JString::cast_local(env, value)?;
                let value: String = value.try_to_string(env)?;
                Ok(PathBuf::from(value))
            })
            .map_err(|e| e.to_string())
    }

    /// Returns NONE for ordinary private paths, OK after committing a selected SAF destination,
    /// or ERROR:<message> if the Android provider refused the write.
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
                        jni_str!("pcCommitIfMapped"),
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

struct AndroidFiles {
    bridge: AndroidFileBridge,
    next_id: AtomicU64,
    queued: Mutex<VecDeque<(PickId, PickRequest)>>,
    active: Mutex<Option<(PickId, PickRequest)>>,
    answers: Mutex<HashMap<PickId, Picked>>,
    save_bytes: Mutex<HashMap<PickId, Vec<u8>>>,
    forgotten: Mutex<HashSet<PickId>>,
    folders: Mutex<HashMap<String, PathBuf>>,
}

impl AndroidFiles {
    fn new(bridge: AndroidFileBridge) -> Self {
        Self {
            bridge,
            next_id: AtomicU64::new(0),
            queued: Mutex::new(VecDeque::new()),
            active: Mutex::new(None),
            answers: Mutex::new(HashMap::new()),
            save_bytes: Mutex::new(HashMap::new()),
            forgotten: Mutex::new(HashSet::new()),
            folders: Mutex::new(HashMap::new()),
        }
    }

    fn enqueue(&self, request: PickRequest, bytes: Option<Vec<u8>>) -> PickId {
        let id = PickId(self.next_id.fetch_add(1, Ordering::Relaxed).wrapping_add(1));
        if let Some(bytes) = bytes {
            self.save_bytes.lock().unwrap_or_else(|e| e.into_inner()).insert(id, bytes);
        }
        self.queued.lock().unwrap_or_else(|e| e.into_inner()).push_back((id, request));
        self.start_next();
        id
    }

    fn start_next(&self) {
        loop {
            let next = {
                let mut active = self.active.lock().unwrap_or_else(|e| e.into_inner());
                if active.is_some() {
                    return;
                }
                let next = self.queued.lock().unwrap_or_else(|e| e.into_inner()).pop_front();
                if let Some((id, request)) = &next {
                    *active = Some((*id, request.clone()));
                }
                next
            };
            let Some((id, request)) = next else {
                return;
            };
            let launch = match request.kind {
                PickKind::Open => self.bridge.request_open(id.0, false),
                PickKind::OpenMany => self.bridge.request_open(id.0, true),
                PickKind::Save => {
                    let name = request.file_name.as_deref()
                        .filter(|name| !name.trim().is_empty())
                        .unwrap_or("Untitled.pcraft");
                    self.bridge.request_save(id.0, name)
                }
                PickKind::Folder => Err("Choosing folders is not supported by this Android file picker yet. Use Open or Save As for individual files.".into()),
            };
            if let Err(error) = launch {
                let failed = self.active.lock().unwrap_or_else(|e| e.into_inner()).take();
                if let Some((failed_id, failed_request)) = failed {
                    self.complete(
                        failed_id,
                        failed_request,
                        Picked::Unavailable(format!("Could not start Android file picker: {error}")),
                    );
                }
                continue;
            }
            return;
        }
    }

    fn complete(&self, id: PickId, request: PickRequest, picked: Picked) {
        self.save_bytes.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
        if self.forgotten.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) {
            return;
        }
        if let Some(path) = picked.first_path() {
            if let Some(parent) = path.parent() {
                self.folders.lock().unwrap_or_else(|e| e.into_inner())
                    .insert(request.purpose.clone(), parent.to_path_buf());
            }
        }
        self.answers.lock().unwrap_or_else(|e| e.into_inner()).insert(id, picked);
    }

    fn poll(&self, ctx: &egui::Context) {
        // Each result is one short JSON object queued by PhotoCraftActivity after picker I/O ends.
        for _ in 0..8 {
            let raw = match self.bridge.poll_result() {
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
            let Some(raw_id) = value.get("id").and_then(serde_json::Value::as_u64) else {
                log::error!("Android picker result has no request id: {raw}");
                continue;
            };
            let active = {
                let mut active = self.active.lock().unwrap_or_else(|e| e.into_inner());
                if active.as_ref().map(|(id, _)| id.0) == Some(raw_id) {
                    active.take()
                } else {
                    None
                }
            };
            let Some((id, request)) = active else {
                log::warn!("Ignoring stale Android picker reply {raw_id}");
                continue;
            };
            let status = value.get("status").and_then(serde_json::Value::as_str).unwrap_or("error");
            let kind = value.get("kind").and_then(serde_json::Value::as_str).unwrap_or("");
            let picked = match status {
                "cancel" => Picked::Cancelled,
                "ok" if kind == "open" => {
                    let paths = value.get("paths")
                        .and_then(serde_json::Value::as_array)
                        .into_iter()
                        .flatten()
                        .filter_map(serde_json::Value::as_str)
                        .map(PathBuf::from)
                        .collect::<Vec<_>>();
                    if paths.is_empty() { Picked::Cancelled } else { Picked::Paths(paths) }
                }
                "ok" if kind == "save" => match value.get("path").and_then(serde_json::Value::as_str) {
                    Some(path) => {
                        let target = PathBuf::from(path);
                        let bytes = self.save_bytes.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                        if let Some(bytes) = bytes {
                            match write_mobile(&self.bridge, path, &bytes) {
                                Ok(()) => Picked::Saved { path: target, file_type: None },
                                Err(error) => Picked::Failed(error),
                            }
                        } else {
                            Picked::Saved { path: target, file_type: None }
                        }
                    }
                    None => Picked::Unavailable("Android save picker returned no destination path.".into()),
                },
                _ => Picked::Unavailable(
                    value.get("message").and_then(serde_json::Value::as_str)
                        .unwrap_or("Android file operation failed").to_owned(),
                ),
            };
            self.complete(id, request, picked);
            ctx.request_repaint();
            self.start_next();
        }
    }
}

impl Files for AndroidFiles {
    fn pick(&self, request: PickRequest) -> PickId {
        self.enqueue(request, None)
    }

    fn take_answer(&self, id: PickId) -> Option<Picked> {
        self.answers.lock().unwrap_or_else(|e| e.into_inner()).remove(&id)
    }

    fn forget(&self, id: PickId) {
        self.answers.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
        self.save_bytes.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
        let active = self.active.lock().unwrap_or_else(|e| e.into_inner());
        if active.as_ref().is_some_and(|(active_id, _)| *active_id == id) {
            self.forgotten.lock().unwrap_or_else(|e| e.into_inner()).insert(id);
            return;
        }
        drop(active);
        self.queued.lock().unwrap_or_else(|e| e.into_inner()).retain(|(queued_id, _)| *queued_id != id);
    }

    fn pending_pick(&self) -> Option<PendingPick> {
        let active = self.active.lock().unwrap_or_else(|e| e.into_inner());
        if let Some((_, request)) = active.as_ref() {
            return Some(PendingPick { request: request.clone(), sheet: false });
        }
        drop(active);
        self.queued.lock().unwrap_or_else(|e| e.into_inner()).front()
            .map(|(_, request)| PendingPick { request: request.clone(), sheet: false })
    }

    fn read(&self, path: &Path) -> Result<Vec<u8>, FileError> {
        fs::read(path).map_err(|error| FileError::Other(format!("{}: {error}", path.display())))
    }

    fn write(&self, path: &Path, bytes: &[u8], _intent: WriteIntent) -> Result<bool, FileError> {
        let path = path.to_string_lossy();
        write_mobile(&self.bridge, path.as_ref(), bytes).map_err(FileError::Other)?;
        Ok(false)
    }

    fn exists(&self, path: &Path) -> bool {
        path.exists()
    }

    fn last_folder(&self, purpose: &str) -> Option<PathBuf> {
        self.folders.lock().unwrap_or_else(|e| e.into_inner()).get(purpose).cloned()
    }

    fn save(&self, mut request: PickRequest, bytes: Vec<u8>) -> PickId {
        request.kind = PickKind::Save;
        self.enqueue(request, Some(bytes))
    }

    fn can_pick(&self) -> bool {
        true
    }

    fn browser_saves(&self) -> bool {
        false
    }
}

fn write_mobile(bridge: &AndroidFileBridge, path: &str, bytes: &[u8]) -> Result<(), String> {
    let target = Path::new(path);
    if let Some(parent) = target.parent().filter(|p| !p.as_os_str().is_empty()) {
        fs::create_dir_all(parent)
            .map_err(|e| format!("Could not create {}: {e}", parent.display()))?;
    }
    let name = target
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("photocraft-output");
    let parent = target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    let temporary = parent.join(format!(".{name}.tmp-{}", std::process::id()));
    fs::write(&temporary, bytes)
        .map_err(|e| format!("Could not write {}: {e}", temporary.display()))?;
    if let Err(error) = fs::rename(&temporary, target) {
        let _ = fs::remove_file(&temporary);
        return Err(format!(
            "Could not finish writing {}: {error}",
            target.display()
        ));
    }
    match bridge.commit_if_mapped(path)? {
        state if state == "NONE" || state == "OK" => Ok(()),
        state if state.starts_with("ERROR:") => Err(state.trim_start_matches("ERROR:").to_owned()),
        state => Err(format!("Unexpected Android save result: {state}")),
    }
}

fn services(bridge: AndroidFileBridge, files: Arc<AndroidFiles>, settings_dir: PathBuf, inbox: Inbox) -> Services {
    let write_bridge = bridge.clone_for_services();
    let save_bridge = bridge.clone_for_services();
    let settings = craft::settings::SettingsStore::<photocraft_engine::prefs::SavedPrefs>::open_at(settings_dir);
    Services {
        // The app's file features use the shared host Files service. Its Android implementation
        // stages SAF selections privately and commits writes back to the selected content URI.
        files: Some(files),
        settings: Some(settings),
        // Files the system asked us to open (ACTION_VIEW/ACTION_SEND) are queued here and drained
        // by the app's own per-frame inbox, exactly like a document chosen in the picker.
        inbox: Some(inbox),
        import: Some(Box::new(
            |name: &str, bytes: &[u8], options: &photocraft_io::ImportOptions| {
                photocraft_io::import_with_options(name, bytes, options)
                    .map(|result| (result.document, result.warnings))
                    .map_err(|error| error.to_string())
            },
        )),
        export: Some(Box::new(
            |doc: &Document, path: &str, settings: &photocraft_ui_egui::ExportSettings| {
                let options = settings.io_options();
                photocraft_io::export(doc, path, &options)
                    .map(|result| (result.bytes, result.warnings))
                    .map_err(|error| error.to_string())
            },
        )),
        // Native .pcraft Save uses save_file rather than export. Route it through the same SAF-aware writer.
        save_file: Some(std::sync::Arc::new(
            move |doc: &Document,
                  path: &str,
                  settings: &photocraft_ui_egui::ExportSettings,
                  ctl: &photocraft_ui_egui::jobs_ui::SaveCtl| {
                ctl.progress(0.0, "Encoding");
                let options = settings.io_options();
                let result = photocraft_io::export(doc, path, &options).map_err(|error| error.to_string())?;
                ctl.commit()?;
                ctl.progress(0.85, "Writing");
                write_mobile(&save_bridge, path, &result.bytes)?;
                ctl.progress(1.0, "");
                Ok(result.warnings)
            },
        )),
        write: Some(Box::new(move |path: &str, bytes: &[u8]| {
            write_mobile(&write_bridge, path, bytes)
        })),
        ..Services::default()
    }
}

// Keep the JavaVM and the AndroidApp cheap to clone into platform-service closures.
impl AndroidFileBridge {
    fn clone_for_services(&self) -> Self {
        Self {
            app: self.app.clone(),
            vm: self.vm.clone(),
        }
    }
}

/// Reconstruct egui's modifier state on Android.
///
/// winit's Android backend delivers `KeyboardInput` events but never emits `ModifiersChanged`
/// (it discards the `KeyEvent`'s meta state), so egui's modifier state stays empty and
/// `Ctrl`/`Alt` shortcuts are ignored while plain keys continue to work. Physical modifier keys
/// do arrive as `Event::Key` events (`Key::ControlLeft`, `Key::AltLeft`, ...), so we track them
/// and stamp the resulting state onto this frame's events. This mirrors `egui-winit`'s
/// `ModifiersChanged` handling and suppresses the text character that would otherwise be emitted
/// alongside a Ctrl/Command shortcut.
fn apply_android_modifiers(state: &mut egui::Modifiers, raw: &mut egui::RawInput) {
    let before = *state;
    let mut kept: Vec<egui::Event> = Vec::with_capacity(raw.events.len());
    for mut event in raw.events.drain(..) {
        match &mut event {
            egui::Event::Key {
                key,
                physical_key,
                pressed,
                modifiers,
                ..
            } => {
                let tracked = physical_key.unwrap_or(*key);
                match tracked {
                    egui::Key::ShiftLeft | egui::Key::ShiftRight => state.shift = *pressed,
                    egui::Key::ControlLeft | egui::Key::ControlRight => state.ctrl = *pressed,
                    egui::Key::AltLeft | egui::Key::AltRight => state.alt = *pressed,
                    _ => {}
                }
                state.mac_cmd = false;
                state.command = state.ctrl;
                *modifiers = *state;
                kept.push(event);
            }
            egui::Event::PointerButton { modifiers, .. } => {
                *modifiers = *state;
                kept.push(event);
            }
            egui::Event::MouseWheel { modifiers, .. } => {
                *modifiers = *state;
                kept.push(event);
            }
            egui::Event::Text(_) if state.ctrl || state.command || state.mac_cmd => {
                // Suppress text emitted with a modifier chord.
            }
            egui::Event::WindowFocused(false) => {
                *state = egui::Modifiers::default();
                kept.push(event);
            }
            _ => kept.push(event),
        }
    }
    raw.events = kept;
    if *state != before {
        // `RawInput` has no modifier field in this egui version: `InputState.modifiers` is driven
        // purely by this event (plus its own per-event copies), so it must be emitted on change.
        raw.events.push(egui::Event::ModifiersChanged(*state));
    }
}


struct PhotoCraftAndroidApp {
    inner: Box<PhotocraftApp>,
    bridge: AndroidFileBridge,
    picker: Arc<AndroidFiles>,
    ime: ime_bridge::ime::ImeBridge,
    modifiers: egui::Modifiers,
    ai_menu: ai_menu::AndroidAiMenu,
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

impl PhotoCraftAndroidApp {
    /// The staged copy of a document, if `path` names one: a *direct* child of the app's own
    /// `media/` directory (see PhotoCraftActivity.newStageFile). Anything else on the device is
    /// never touched.
    fn staged_media_file(&self, path: &str) -> Option<PathBuf> {
        let files = self.bridge.files_dir().ok()?;
        let media = files.join("media");
        let file = PathBuf::from(path);
        (file.parent() == Some(media.as_path())).then_some(file)
    }

    /// Delete every staged copy under `media/` that neither the recent list nor an open document
    /// refers to, sparing files written in the last minute (a document may be mid-import). This
    /// clears out copies orphaned before this pruning existed, or by an app killed mid-session.
    fn staged_sweep_orphans(bridge: &AndroidFileBridge, recent: &[String], open: &[String]) {
        let Ok(files) = bridge.files_dir() else { return };
        let media = files.join("media");
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
        let current: Vec<String> = self.inner.ui.recent_files.to_vec();
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
}

impl eframe::App for PhotoCraftAndroidApp {
    fn logic(&mut self, ctx: &egui::Context, frame: &mut eframe::Frame) {
        self.picker.poll(ctx);
        // Deliver any file the system asked us to open through the app's own inbox.
        drain_incoming(&self.bridge, &self.intent_inbox, &mut self.intent_warmup);
        self.staged_prune_tick();
        self.inner.logic(ctx, frame);
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        system_fonts::install_system_fonts(ui.ctx());
        // Native menu; unimplemented actions remain disabled until backend verification.
        if self.ai_menu.show(ui, &mut self.inner.session) {
            self.inner.sync_views();
        }
        self.inner.ui(ui, _frame);
    }

    fn raw_input_hook(&mut self, ctx: &egui::Context, raw: &mut egui::RawInput) {
        self.ime.poll(raw);
        apply_android_modifiers(&mut self.modifiers, raw);
        self.inner.raw_input_hook(ctx, raw);
    }
}

#[cfg(target_os = "android")]
#[unsafe(no_mangle)]
fn android_main(android_app: AndroidApp) {
    log::info!("{ANDROID_SHELL_MARKER} ready; {}", ime_bridge::ime::IME_MARKER);
    system_fonts::install_font_env(&android_app);
    let bridge = match AndroidFileBridge::new(android_app.clone()) {
        Ok(bridge) => bridge,
        Err(error) => {
            log::error!("PhotoCraft Android startup failed: {error}");
            return;
        }
    };
    let files_dir = match bridge.files_dir() {
        Ok(path) => path,
        Err(error) => {
            log::error!("Could not locate PhotoCraft app-private storage: {error}");
            return;
        }
    };
    let settings_dir = files_dir.join("PhotoCraft");
    if let Err(error) = fs::create_dir_all(&settings_dir) {
        log::error!("Could not create preferences directory: {error}");
        return;
    }
    let picker = Arc::new(AndroidFiles::new(bridge.clone_for_services()));
    let intent_inbox: Inbox = Arc::new(Mutex::new(Vec::new()));
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("PhotoCraft")
            .with_drag_and_drop(true),
        // Match PhotoCraft's GPU rendering path rather than relying on the
        // window renderer default selected by the Android shell.
        renderer: eframe::Renderer::Wgpu,
        android_app: Some(android_app),
        ..Default::default()
    };
    let app_bridge = bridge.clone_for_services();
    let app_picker = picker.clone();
    let app_intent_inbox = intent_inbox.clone();
    let result = eframe::run_native(
        "PhotoCraft",
        options,
        Box::new(move |cc| {
            PhotocraftApp::setup_context(&cc.egui_ctx, photocraft_ui_egui::theme::AppTheme::pro());
            let mut app = PhotocraftApp::new(
                Session::new(),
                services(
                    app_bridge.clone_for_services(),
                    app_picker.clone(),
                    settings_dir.clone(),
                    app_intent_inbox.clone(),
                ),
            );

            // eframe drawing a window through wgpu does not automatically enable
            // PhotoCraft's own GPU image compositor. Pass the *same* render state
            // to PhotoCraft and publish its adapter details for Help > System Info.
            // Keep intentional CPU rendering preferences and a CPU-only adapter
            // as CPU, rather than forcing GPU work onto a software rasterizer.
            if let Some(rs) = cc.wgpu_render_state.clone() {
                let adapter = rs.adapter.get_info();
                log::info!(
                    "PhotoCraft Android GPU adapter: {} | backend: {:?} | device: {:?} | driver: {}",
                    adapter.name,
                    adapter.backend,
                    adapter.device_type,
                    adapter.driver,
                );
                app.perf.gpu_info.set_adapter(&adapter);

                if adapter.device_type == eframe::wgpu::DeviceType::Cpu {
                    log::warn!("PhotoCraft Android selected a software graphics adapter; keeping CPU canvas");
                    app.perf.gpu_info.fallback = Some(
                        "No compatible hardware graphics adapter; using CPU compositing.".into(),
                    );
                } else if std::env::var_os("PHOTOCRAFT_CPU_CANVAS").is_some()
                    || app.session.prefs().performance.effective_rendering_mode()
                        == photocraft_engine::prefs::RenderingMode::Cpu
                {
                    log::info!("PhotoCraft Android CPU canvas is selected in preferences/environment");
                } else {
                    app.set_wgpu(rs);
                    log::info!(
                        "PhotoCraft Android image compositor after GPU setup: {}",
                        app.perf.gpu_info.canvas
                    );
                }
            } else {
                log::warn!("PhotoCraft Android has no wgpu render state; keeping CPU canvas");
                app.perf.gpu_info.fallback = Some(
                    "The Android window did not provide a wgpu graphics device.".into(),
                );
            }

            Ok(Box::new(PhotoCraftAndroidApp {
                inner: app,
                bridge: app_bridge.clone_for_services(),
                picker: app_picker.clone(),
                ime: ime_bridge::ime::ImeBridge::new(&app_bridge.app),
                modifiers: egui::Modifiers::default(),
                ai_menu: ai_menu::AndroidAiMenu::new(settings_dir.join("ai-tools-visible")),
                intent_inbox: app_intent_inbox.clone(),
                intent_warmup: 2,
                staged_seen: Vec::new(),
                staged_sweep_at: Some(std::time::Instant::now() + std::time::Duration::from_secs(30)),
            }))
        }),
    );
    if let Err(error) = result {
        log::error!("PhotoCraft Android exited with an error: {error}");
    }
}
