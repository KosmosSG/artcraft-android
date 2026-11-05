"""Handle Android Escape before widgets filter it, using the foreground operation."""
import argparse
from pathlib import Path
from photocraft_v0201_keyboard_diagnostics_overlay import patch

parser = argparse.ArgumentParser()
for name in ("upstream", "adapter", "vendor"):
    parser.add_argument("--" + name, type=Path, required=True)
a = parser.parse_args()
host = a.adapter / "src/lib.rs"
menus = a.upstream / "crates/ui-egui/src/menus.rs"
native = a.vendor / "android-activity/src/native_activity/mod.rs"
library = a.vendor / "android-activity/src/lib.rs"
activity = a.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
patch(a.adapter / "Cargo.toml", 'version = "0.20.1-android.6"', 'version = "0.20.1-android.7"')

with menus.open("a") as f:
    f.write("""
#[cfg(target_os = "android")]
pub fn pc_cancel_owner(app: &crate::PhotocraftApp) -> u8 {
    if app.discard.is_some() { return 2; }
    if let Some(dialog) = app.ui.dialogs.last() {
        return if dialog.kind == crate::state::DialogKind::NewDocument { 3 } else { 0 };
    }
    u8::from(app.ui.text_edit.is_some())
}

#[cfg(target_os = "android")]
pub fn pc_cancel(app: &mut crate::PhotocraftApp, owner: u8) {
    match owner {
        2 => app.discard = None,
        3 => if let Some(id) = app.ui.dialogs.last().map(|d| d.id) {
            let _ = crate::dialogs::cancel(app, id);
        },
        1 => { crate::type_tool::commit(app); }
        _ => {}
    }
}
""")
patch(library, "pub fn photocraft_input_owner(editing: bool, dialog: bool) {\n    let owner = if dialog { 2 } else { u8::from(editing) };",
      """static PC_CANCEL: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);
pub fn pc_take_cancel() -> u8 { PC_CANCEL.swap(0, std::sync::atomic::Ordering::AcqRel) }
pub fn photocraft_input_owner(owner: u8) {""")
patch(native, "            let owned = match &ndk_event {", """            if let ndk::event::InputEvent::KeyEvent(e) = &ndk_event {
                let ptr = e.ptr().as_ptr();
                let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(ptr) as u32 };
                let scan = unsafe { ndk_sys::AKeyEvent_getScanCode(ptr) };
                if owner != 0 && (code == ndk_sys::AKEYCODE_ESCAPE ||
                    (e.device_id() > 0 && (scan == 1 || code == ndk_sys::AKEYCODE_BACK))) {
                    if unsafe { ndk_sys::AKeyEvent_getAction(ptr) } == 0 &&
                        unsafe { ndk_sys::AKeyEvent_getRepeatCount(ptr) } == 0 {
                        crate::PC_CANCEL.store(owner, std::sync::atomic::Ordering::Release);
                    }
                    queue.finish_event(ndk_event, true);
                    return true;
                }
            }
            let owned = match &ndk_event {""")
patch(activity, "    public void pcSetCursor(", """    private volatile boolean pcOwnsCancel;
    public void pcSetCancel(boolean owned) { pcOwnsCancel = owned; }
    @Override public void onBackPressed() {
        if (pcOwnsCancel) artcraftHardwareKeys.offer("111,0,1");
        else super.onBackPressed();
    }
    public void pcSetCursor(""")
patch(activity, "        int code = event.getKeyCode(), action = event.getAction();", """        int code = event.getKeyCode(), action = event.getAction();
        if (pcOwnsCancel && event.getDeviceId() > 0
                && (code == KeyEvent.KEYCODE_BACK || event.getScanCode() == 1)) code = KeyEvent.KEYCODE_ESCAPE;""")
patch(host, "    fn toggle_startup_updates(", """    fn pc_set_cancel(&self, owned: bool) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("pcSetCancel"), jni_sig!("(Z)V"), &[JValue::Bool(owned)])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn toggle_startup_updates(""")
patch(host, "artcraft_esc_pending: bool,", "pc_previous_owner: u8,")
patch(host, "artcraft_esc_pending: false,", "pc_previous_owner: 0,")
source = host.read_text()
start = source.index("        if self.artcraft_esc_pending")
end = source.index("        if pc_typing_before_ui", start)
patch(host, source[start:end], "")
start = source.index("        android_activity::photocraft_input_owner(")
end = source.index("        );",start) + len("        );")
patch(host, source[start:end], """        let owner = photocraft_ui_egui::menus::pc_cancel_owner(&self.inner);
        android_activity::photocraft_input_owner(owner);
        if owner != self.pc_previous_owner && self.bridge.pc_set_cancel(owner != 0).is_ok() {
            self.pc_previous_owner = owner;
        }
        if owner != 0 {
            ui.ctx().request_repaint_after(std::time::Duration::from_millis(100));
        }""")
start = source.index("        // Store commands before")
end = source.index("        self.canvas_gesture.route",start)
patch(host, source[start:end], """        let owner = photocraft_ui_egui::menus::pc_cancel_owner(&self.inner);
        let native = android_activity::pc_take_cancel();
        let escape = raw.events.iter().any(|e| matches!(e, egui::Event::Key {
            key: egui::Key::Escape, pressed: true, repeat: false, .. }));
        if owner != 0 && (native == owner || escape) {
            raw.events.retain(|e| !matches!(e, egui::Event::Key { key: egui::Key::Escape, .. }));
            photocraft_ui_egui::menus::pc_cancel(&mut self.inner, owner);
            let _ = self.bridge.hide_native_keyboard();
            ctx.memory_mut(|m| { if let Some(id) = m.focused() { m.surrender_focus(id); } });
            self.pc_keyboard_diag.push(format!("Escape handled: owner={owner} native={native}"));
            ctx.request_repaint();
        }
""")
patch(host, "    log::info!(\"{ANDROID_SHELL_MARKER}", """    android_activity::photocraft_input_owner(0);
    android_activity::pc_take_cancel();
    log::info!("{ANDROID_SHELL_MARKER}""")
