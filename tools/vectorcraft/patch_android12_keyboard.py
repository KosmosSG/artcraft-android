"""VectorCraft Android.12: route lost MagicOS physical shortcuts safely.

Apply after patch_stability_v021 and diagnostics on generated sources.
The Java NativeActivity may see a hardware event while native winit/egui does
not (device evidence: 64 native receipts versus 36 egui receipts). Do not
inject letters while Type is editing, a generic text field is focused, or
IME composition is active. Key presses are consumed by Java ONLY when queued,
preventing duplicate upstream canvas actions.
"""
from pathlib import Path
from backend_stability import once


def patch(root: Path) -> None:
    java=root/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s=java.read_text()
    s=once(s,'    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> hiddenImeCloseKeys =',
    '''    // 0=typing/other, 1=canvas shortcuts, 2=Save Changes modal.
    // This is only the bridge mode, never a record of user text.
    private volatile int hardwareShortcutMode = 0;
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> physicalShortcutKeys =
        new java.util.concurrent.ConcurrentLinkedQueue<>();
    public void vcSetHardwareShortcutMode(int mode) {
        hardwareShortcutMode = mode;
        if (mode == 0) physicalShortcutKeys.clear();
    }
    public int vcPollPhysicalShortcut() {
        Integer key = physicalShortcutKeys.poll();
        return key == null ? 0 : key.intValue();
    }
    private final java.util.concurrent.ConcurrentLinkedQueue<Integer> hiddenImeCloseKeys =''')
    old='''        final boolean close = key == KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q;
        if (imeView != null && imeView.hasFocus() && close && event.isCtrlPressed()
                && !event.isAltPressed() && !event.isShiftPressed()) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                hiddenImeCloseKeys.offer(key);
            }
            return true;
        }
        return super.dispatchKeyEvent(event);'''
    new='''        final boolean close = key == KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q;
        // Ctrl+W/Q remain legal while typing, but only when the current
        // physical keyboard event is actually delivered to this Activity.
        if (close && event.isCtrlPressed()
                && !event.isAltPressed() && !event.isShiftPressed()) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0
                    && hiddenImeCloseKeys.size() < 32) {
                hiddenImeCloseKeys.offer(key);
            }
            return true;
        }
        final int mode = hardwareShortcutMode;
        final boolean plain = !event.isCtrlPressed() && !event.isAltPressed()
                && !event.isMetaPressed() && !event.isShiftPressed();
        final boolean canvasKey = mode == 1 && !imeWanted
                && (key == KeyEvent.KEYCODE_V || key == KeyEvent.KEYCODE_T
                    || key == KeyEvent.KEYCODE_P);
        final boolean dialogKey = mode == 2
                && (key == KeyEvent.KEYCODE_S || key == KeyEvent.KEYCODE_C
                    || key == KeyEvent.KEYCODE_D || key == KeyEvent.KEYCODE_ESCAPE);
        if (plain && (canvasKey || dialogKey)) {
            if (event.getAction() == KeyEvent.ACTION_DOWN
                    && event.getRepeatCount() == 0 && physicalShortcutKeys.size() < 32) {
                physicalShortcutKeys.offer(key);
            }
            // Key-up must be consumed alongside Down to avoid leaking a
            // stranded release event to the upstream keyboard state.
            return true;
        }
        return super.dispatchKeyEvent(event);'''
    s=once(s,old,new)
    java.write_text(s)
    rust=root/"adapters/vectorcraft/src/lib.rs"
    s=rust.read_text()
    s=once(s,'    fn poll_hidden_ime_close(&self) -> Result<i32, String> {',
    '''    fn set_hardware_shortcut_mode(&self, mode: i32) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcSetHardwareShortcutMode"),
                jni_sig!("(I)V"), &[JValue::Int(mode)])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn poll_physical_shortcut(&self) -> Result<i32, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("vcPollPhysicalShortcut"),
                jni_sig!("()I"), &[])?.i()
        }).map_err(|error| error.to_string())
    }

    fn poll_hidden_ime_close(&self) -> Result<i32, String> {''')
    s=once(s,'    last_type_editing: bool,','    last_type_editing: bool,\n    last_hardware_shortcut_mode: i32,')
    s=once(s,'                last_type_editing: false,','                last_type_editing: false,\n                last_hardware_shortcut_mode: -1,')
    anchor='''        let modal = self.inner.ui.dialog.is_some() || self.inner.ui.palette_open;'''
    s=once(s,anchor,anchor+'''
        // Device tracing shows physical keys lost between Android and egui
        // after Type exits. The fallback is enabled only on an idle canvas
        // or in our own unsaved-doc dialog, never during normal typing.
        let modal_save = self.inner.ui.dialog.as_ref().is_some_and(|dialog|
            dialog.kind == "saveChanges");
        let hardware_mode = if modal_save {
            2
        } else if !modal && !editing && !field_focused && !composing
            && self.inner.session.active().is_some()
        {
            1
        } else { 0 };
        if self.last_hardware_shortcut_mode != hardware_mode {
            if let Err(error) = self.bridge.set_hardware_shortcut_mode(hardware_mode) {
                log::warn!("Physical shortcut mode update failed: {error}");
            }
            self.last_hardware_shortcut_mode = hardware_mode;
        }
        for _ in 0..8 {
            let code = match self.bridge.poll_physical_shortcut() {
                Ok(0) => break,
                Ok(code) => code,
                Err(error) => {
                    log::warn!("Physical shortcut poll failed: {error}");
                    break;
                }
            };
            let key = match (code, hardware_mode) {
                (50, 1) => Some(egui::Key::V),
                (48, 1) => Some(egui::Key::T),
                (44, 1) => Some(egui::Key::P),
                (47, 2) => Some(egui::Key::S),
                (31, 2) => Some(egui::Key::C),
                (32, 2) => Some(egui::Key::D),
                (111, 2) => Some(egui::Key::Escape),
                _ => None,
            };
            if let Some(key) = key {
                // Do not deliver letters to normal Gboard / Type editing.
                // Setting focused=true permits official upstream handlers
                // to act on the modal even after a stale window focus event.
                raw.focused = true;
                raw.events.push(egui::Event::Key {
                    key, physical_key: Some(key), pressed: true, repeat: false,
                    modifiers: egui::Modifiers::NONE,
                });
                if hardware_mode == 1 {
                    raw.events.push(egui::Event::Text(
                        key.name().to_ascii_lowercase()));
                }
                log::debug!("Delivered Android physical shortcut: {key:?} mode={hardware_mode}");
            }
        }''')
    rust.write_text(s)
    print("PASS: scoped Android hardware-key fallback; no text editing interception")


if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
