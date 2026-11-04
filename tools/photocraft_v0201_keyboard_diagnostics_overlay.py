#!/usr/bin/env python3
"""Temporary-only, opt-in PhotoCraft v0.20.1 keyboard route diagnostics.

Runs AFTER Android 5/6/7 overlays on an isolated CI checkout. Does not
change the published baseline, production signer, or installed user data.
Does NOT inspect or save typed text, tokens, clipboard, or documents.
"""
from pathlib import Path
import argparse
import subprocess

PIN = "327c4cc82e737a3e0af7c147a477126d77525495"

def patch(path: Path, before: str, after: str) -> None:
    data = path.read_text(encoding="utf-8")
    count = data.count(before)
    if count != 1:
        raise RuntimeError(f"Keyboard diagnostics: unsafe anchor in {path}: {count}")
    path.write_text(data.replace(before, after, 1), encoding="utf-8")
    print(f"Keyboard diagnostics staged: {path}")

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--upstream", required=True, type=Path)
    cli.add_argument("--adapter", required=True, type=Path)
    opt = cli.parse_args()
    sha = subprocess.check_output(["git", "-C", str(opt.upstream), "rev-parse", "HEAD"], text=True).strip()
    if sha != PIN:
        raise RuntimeError(f"Unreviewed upstream {sha}")
    host = opt.adapter / "src/lib.rs"
    act = opt.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    brand = opt.upstream / "crates/ui-egui/src/panels/brand.rs"

    # The diagnostics launcher is in the blue Pc menu; default is OFF.
    patch(brand,
'''                action(ui, "Toggle Update Check at Startup", 9);
            });
            ui.separator();
''',
'''                action(ui, "Toggle Update Check at Startup", 9);
            });
            ui.separator();
            action(ui, "Keyboard Diagnostics (test)…", 18);
            ui.separator();
''')

    # Only records physical keycodes in a fixed shortcut allowlist.
    # No text, composition contents, clipboard, tokens or files are read.
    # Events stay in memory and the capture switch defaults to disabled.
    patch(act,
'''    private long artcraftLastKeyTime = -1L;
''',
'''    private volatile boolean pcDiagEnabled = false;
    private final ConcurrentLinkedQueue<String> pcDiagKeys = new ConcurrentLinkedQueue<>();
    public void pcKeyDiagSetEnabled(boolean enabled) {
        pcDiagEnabled = enabled;
        pcDiagKeys.clear();
    }
    public String pcKeyDiagPoll() { return pcDiagKeys.poll(); }
    public String pcKeyDiagState() {
        EditText host = imeView;
        return "Window focus: " + hasWindowFocus()
            + " | Hidden EditText focus: " + (host != null && host.hasFocus())
            + " | IME requested: " + imeWanted;
    }
    private void pcKeyDiagCapture(KeyEvent e, String route) {
        if (!pcDiagEnabled || e.getAction() != KeyEvent.ACTION_DOWN
                || e.getRepeatCount() != 0) return;
        int code = e.getKeyCode();
        // Keep only task-relevant shortcut keys, never raw text.
        boolean allowed = code == KeyEvent.KEYCODE_ESCAPE
            || code == KeyEvent.KEYCODE_ENTER
            || code == KeyEvent.KEYCODE_W || code == KeyEvent.KEYCODE_Y
            || code == KeyEvent.KEYCODE_N || code == KeyEvent.KEYCODE_C
            || code == KeyEvent.KEYCODE_M || code == KeyEvent.KEYCODE_V
            || code == KeyEvent.KEYCODE_T || code == KeyEvent.KEYCODE_B
            || code == KeyEvent.KEYCODE_L || code == KeyEvent.KEYCODE_E
            || code == KeyEvent.KEYCODE_G || code == KeyEvent.KEYCODE_H
            || code == KeyEvent.KEYCODE_Z || code == KeyEvent.KEYCODE_D
            || code == KeyEvent.KEYCODE_S;
        if (!allowed || pcDiagKeys.size() >= 40) return;
        pcDiagKeys.offer(route + " | " + KeyEvent.keyCodeToString(code)
            + (e.isCtrlPressed() ? " +Ctrl" : "")
            + (e.isAltPressed() ? " +Alt" : "")
            + (e.isShiftPressed() ? " +Shift" : ""));
    }

    private long artcraftLastKeyTime = -1L;
''')

    patch(act,
'''    public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
''',
'''    public boolean dispatchKeyEvent(KeyEvent event) {
        pcKeyDiagCapture(event, "Activity.dispatchKeyEvent");
        int code = event.getKeyCode();
''')
    patch(act,
'''    public boolean dispatchKeyShortcutEvent(KeyEvent event) {
        // Preserve Ctrl shortcuts even when an OEM routes them separately.
''',
'''    public boolean dispatchKeyShortcutEvent(KeyEvent event) {
        pcKeyDiagCapture(event, "Activity.dispatchKeyShortcutEvent");
        // Preserve Ctrl shortcuts even when an OEM routes them separately.
''')
    patch(act,
'''                public boolean onKeyPreIme(int keyCode, KeyEvent event) {
                    // Some tablet IMEs intercept Y/N/C and tool letters before
''',
'''                public boolean onKeyPreIme(int keyCode, KeyEvent event) {
                    pcKeyDiagCapture(event, "EditText.onKeyPreIme");
                    // Some tablet IMEs intercept Y/N/C and tool letters before
''')
    patch(act,
'''                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    pcRememberHardwareKey(event);
''',
'''                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    pcKeyDiagCapture(event, "EditText.onKeyDown");
                    pcRememberHardwareKey(event);
''')
    patch(act,
'''                        public boolean sendKeyEvent(KeyEvent event) {
                            pcRememberHardwareKey(event);
''',
'''                        public boolean sendKeyEvent(KeyEvent event) {
                            pcKeyDiagCapture(event, "InputConnection.sendKeyEvent");
                            pcRememberHardwareKey(event);
''')

    # Access diagnostic Java methods via the same already-approved JNI bridge.
    patch(host,
'''    fn poll_hardware_key(&self) -> Result<Option<String>, String> {
''',
'''    fn pc_diag_set_enabled(&self, enabled: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcKeyDiagSetEnabled"),
                jni_sig!("(Z)V"), &[JValue::Bool(enabled)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn pc_diag_poll(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcKeyDiagPoll"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn pc_diag_state(&self) -> Result<String, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<String> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(&*activity, jni_str!("pcKeyDiagState"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            let value = JString::cast_local(env, result)?;
            value.try_to_string(env)
        }).map_err(|e| e.to_string())
    }

    fn poll_hardware_key(&self) -> Result<Option<String>, String> {
''')

    # This viewer only keeps a rolling in-memory buffer of shortcut KEY NAMES.
    # It intentionally cannot see, store or export actual typed characters.
    patch(host,
'''impl eframe::App for PhotoCraftAndroidApp {
''',
'''#[derive(Default)]
struct PcKeyboardDiagnostics {
    visible: bool,
    events: std::collections::VecDeque<String>,
    android_state: String,
    last_state_check: Option<std::time::Instant>,
}
impl PcKeyboardDiagnostics {
    fn push(&mut self, line: String) {
        if !self.visible { return; }
        if self.events.len() >= 24 { self.events.pop_front(); }
        self.events.push_back(line);
    }
    fn note_keys(&mut self, source: &str, raw: &egui::RawInput) {
        if !self.visible { return; }
        for event in &raw.events {
            if let egui::Event::Key { key, pressed: true, modifiers, .. } = event {
                if matches!(key, egui::Key::M | egui::Key::V | egui::Key::T
                    | egui::Key::B | egui::Key::L | egui::Key::W
                    | egui::Key::E | egui::Key::G | egui::Key::H
                    | egui::Key::Z | egui::Key::Y | egui::Key::N
                    | egui::Key::C | egui::Key::Escape) {
                    self.push(format!("{source} | {key:?}{}",
                        if modifiers.ctrl { " +Ctrl" } else { "" }));
                }
            }
        }
    }
    fn show(&mut self, ctx: &egui::Context, type_active: bool,
        focused_text_field: bool, discard_modal: bool) {
        if !self.visible { return; }
        let mut open = self.visible;
        egui::Window::new("Keyboard Diagnostics · PhotoCraft Test")
            .open(&mut open).resizable(true).show(ctx, |ui| {
                ui.strong("Keyboard routing · no text contents captured");
                ui.label(&self.android_state);
                ui.label(format!(
                    "PhotoCraft Type editing: {type_active} | egui text focus: {focused_text_field} | Save/Discard dialog: {discard_modal}"
                ));
                ui.label("Android event missing = keyboard/OS interception.");
                ui.label("Android present, post-bridge absent = JNI/input routing.");
                ui.label("Post-bridge present, tool unchanged = focus/command dispatch.");
                if ui.button("Clear observations").clicked() { self.events.clear(); }
                ui.separator();
                egui::ScrollArea::vertical().max_height(280.0).show(ui, |ui| {
                    if self.events.is_empty() {
                        ui.label("Press M/V, then T → type → ESC → M, or Ctrl+W → Y/N/C.");
                    }
                    for line in self.events.iter().rev() {
                        ui.monospace(line);
                    }
                });
                ui.small("Temporary test panel. Screenshot for troubleshooting. No telemetry.");
            });
        self.visible = open;
    }
}

impl eframe::App for PhotoCraftAndroidApp {
''')

    patch(host,
'''    artcraft_type_ime_was_active: bool,
''',
'''    artcraft_type_ime_was_active: bool,
    pc_keyboard_diag: PcKeyboardDiagnostics,
''')
    patch(host,
'''                artcraft_type_ime_was_active: false,
''',
'''                artcraft_type_ime_was_active: false,
                pc_keyboard_diag: PcKeyboardDiagnostics::default(),
''')

    patch(host,
'''            13..=16 => {
''',
'''            18 => {
                self.pc_keyboard_diag.visible = !self.pc_keyboard_diag.visible;
                self.pc_keyboard_diag.events.clear();
                if let Err(error) = self.bridge.pc_diag_set_enabled(self.pc_keyboard_diag.visible) {
                    self.pc_keyboard_diag.push(format!("Java diagnostics unavailable: {error}"));
                }
            }
            13..=16 => {
''')

    patch(host,
'''        self.ime.poll(raw);
''',
'''        // Observe the original native egui input BEFORE Java bridge injection.
        self.pc_keyboard_diag.note_keys("Native/egui", raw);
        self.ime.poll(raw);
''')

    patch(host,
'''        self.shortcut_pad.inject_controls(raw);
''',
'''        self.shortcut_pad.inject_controls(raw);
        self.pc_keyboard_diag.note_keys("After bridge", raw);
        if self.pc_keyboard_diag.visible {
            for _ in 0..12 {
                match self.bridge.pc_diag_poll() {
                    Ok(Some(value)) => self.pc_keyboard_diag.push(format!("Android | {value}")),
                    Ok(None) => break,
                    Err(error) => {
                        self.pc_keyboard_diag.push(format!("Java poll error: {error}"));
                        break;
                    }
                }
            }
        }
''')
    patch(host,
'''        if let Some(command) = self.artcraft_tool_pending.take() {
''',
'''        if let Some(command) = self.artcraft_tool_pending.take() {
            self.pc_keyboard_diag.push(format!("Tool command attempted: {command}"));
''')
    patch(host,
'''                if key != 0 {
                    photocraft_ui_egui::menus::artcraft_queue_dialog_key(key);
''',
'''                if key != 0 {
                    self.pc_keyboard_diag.push(format!("Discard dialog key queued: {key}"));
                    photocraft_ui_egui::menus::artcraft_queue_dialog_key(key);
''')

    patch(host,
'''        self.inner.ui(ui, _frame);
        // The in-app Pc mark is a menu launcher; act only after upstream
''',
'''        self.inner.ui(ui, _frame);
        // The in-app Pc mark is a menu launcher; act only after upstream
''') if False else None  # The original UI body is altered by the prior pad overlay.

    # Render immediately before the verified Pc action match. Newly toggled
    # diagnostics appear next UI frame; closing X disables Java capture.
    patch(host,
'''        match pc_action {
''',
'''        if self.pc_keyboard_diag.visible
            && self.pc_keyboard_diag.last_state_check.is_none_or(|at|
                at.elapsed() >= std::time::Duration::from_millis(250))
        {
            self.pc_keyboard_diag.android_state = self.bridge.pc_diag_state()
                .unwrap_or_else(|error| format!("Android state unavailable: {error}"));
            self.pc_keyboard_diag.last_state_check = Some(std::time::Instant::now());
        }
        let was_visible = self.pc_keyboard_diag.visible;
        self.pc_keyboard_diag.show(ui.ctx(),
            self.inner.ui.text_edit.is_some(),
            ui.ctx().text_edit_focused(),
            photocraft_ui_egui::menus::artcraft_discard_active(&self.inner));
        if was_visible && !self.pc_keyboard_diag.visible {
            let _ = self.bridge.pc_diag_set_enabled(false);
            self.pc_keyboard_diag.events.clear();
        }
        match pc_action {
''')

    for expected in ("pcKeyDiagSetEnabled", "pcKeyDiagPoll", "pcKeyDiagState",
            "Native/egui", "After bridge", "Tool command attempted",
            "Discard dialog key queued", "Keyboard Diagnostics (test)", "pc_keyboard_diag.show"):
        combined = host.read_text() + act.read_text() + brand.read_text()
        if expected not in combined:
            raise RuntimeError(f"Missing diagnostic component: {expected}")
    print("PASS: opt-in keyboard routing diagnostics staged; no text or clipboard capture")

if __name__ == "__main__":
    main()
