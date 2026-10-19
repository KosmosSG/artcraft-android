1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
//! Builder-owned Android shell for PhotoCraft.
//! Platform file operations use Android's Storage Access Framework (SAF). Selected documents
//! are staged inside app-private storage, with a persistent URI mapping used to write saved bytes
//! back through ContentResolver. The upstream PhotoCraft crates remain unchanged.
//! ARTCRAFT_PHOTOCRAFT_SAF_JNI022_FIX_V1

use android_activity::AndroidApp;
use jni::{
    JavaVM, jni_sig, jni_str,
    objects::{JObject, JString, JValue},
};
use photocraft_codecs::{ChannelLayout, EncodeOptions, Image};
use photocraft_doc::Document;
use photocraft_engine::Session;
use photocraft_ui_egui::{
    FileDialogAnswer, FileDialogReply, FileDialogRequest, Inbox, PhotocraftApp, Services,
};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

// Shared with the generated launchers: brings the device's own system fonts into the egui fallback
// chain and makes them visible to the app's own font scanners (see templates/android/system_fonts.rs).
mod system_fonts;
// Register an imported font with PhotoCraft's text engine.
fn register_custom_font(bytes: Vec<u8>) -> Result<Vec<String>, String> {
    if bytes.is_empty() || bytes.len() > 32 * 1024 * 1024 {
        return Err("Font file must be between 1 byte and 32 MB".into());
    }

    let mut engine = photocraft_text::shared()
        .lock()
        .map_err(|e| format!("Font engine lock failed: {e}"))?;

    let families = engine.fonts.register_font_data(bytes);

    if families.is_empty() {
        return Err("No supported font families found".into());
    }

    Ok(families)
}
// Reload private fonts before opening the editor.
fn load_custom_fonts(files_dir: &Path) {
    let Ok(entries) = fs::read_dir(files_dir.join("custom-fonts")) else { return };
    for entry in entries.flatten() {
        let path = entry.path();
        let valid_extension = path.extension().and_then(|v| v.to_str())
            .is_some_and(|v| v.eq_ignore_ascii_case("ttf") || v.eq_ignore_ascii_case("otf"));
        if !valid_extension || !path.is_file() { continue; }
        if !fs::metadata(&path).is_ok_and(|m| m.len() > 0 && m.len() <= 32 * 1024 * 1024) { continue; }
        match fs::read(&path).map_err(|e| e.to_string()).and_then(register_custom_font) {
            Ok(families) => log::info!("Restored custom font {:?}: {:?}", path, families),
            Err(error) => log::warn!("Could not restore custom font {:?}: {error}", path),
        }
    }
}

// Shared with the generated launchers: turns Android's soft keyboard into egui IME events (see
// templates/android/ime_bridge.rs). The `mod ime_bridge;` marker also keeps the vendored
// android-activity, which forwards show/hide to this Activity's imeShow/imeHide, in step.
mod ime_bridge;

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
