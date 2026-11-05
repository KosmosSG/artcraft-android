"""Route physical editor and prompt shortcuts before NativeActivity offers them to the IME."""
from pathlib import Path
import argparse
from photocraft_v0201_keyboard_diagnostics_overlay import patch

p = argparse.ArgumentParser()
p.add_argument('--adapter', type=Path, required=True)
p.add_argument('--vendor', type=Path, required=True)
args = p.parse_args()
host = args.adapter / 'src/lib.rs'
vendor = args.vendor / 'android-activity/src'
patch(args.adapter/'Cargo.toml', 'version = "0.20.1-android.4"', 'version = "0.20.1-android.5"')
with (vendor/'lib.rs').open('a') as f:
    f.write("""
static PHOTOCRAFT_INPUT_OWNER: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);

/// Published by the PhotoCraft candidate after drawing the active editor or dialog.
pub fn photocraft_input_owner(editing: bool, dialog: bool) {
    let owner = if dialog { 2 } else { u8::from(editing) };
    PHOTOCRAFT_INPUT_OWNER.store(owner, std::sync::atomic::Ordering::Release);
}
""")
patch(vendor/'native_activity/mod.rs', '            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {', '''            // The system IME may consume a hardware press before winit sees it.
            // Keep only commands owned by the foreground editor/dialog on the native path.
            let owner = crate::PHOTOCRAFT_INPUT_OWNER.load(std::sync::atomic::Ordering::Acquire);
            let owned = match &ndk_event {
                ndk::event::InputEvent::KeyEvent(e) if owner != 0 && e.device_id() > 0 => {
                    // Same borrowed NDK key accessor used by input::KeyEvent::key_code.
                    let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(e.ptr().as_ptr()) as u32 };
                    code == ndk_sys::AKEYCODE_ESCAPE
                        || (owner == 2 && matches!(code,
                            ndk_sys::AKEYCODE_Y | ndk_sys::AKEYCODE_N | ndk_sys::AKEYCODE_C))
                }
                _ => false,
            };
            let next = if owned { Some(ndk_event) } else { queue.pre_dispatch(ndk_event) };
            if let Some(ndk_event) = next {''')
patch(host, '        self.android_fonts.show(ui.ctx());', '''        self.android_fonts.show(ui.ctx());
        android_activity::photocraft_input_owner(
            self.inner.ui.text_edit.is_some() && !ui.ctx().text_edit_focused(),
            photocraft_ui_egui::menus::artcraft_discard_active(&self.inner),
        );''')
patch(host, 'let pc_typing = self.inner.ui.text_edit.is_some() || ctx.text_edit_focused();',
      '''let pc_dialog = photocraft_ui_egui::menus::artcraft_discard_active(&self.inner);
        let pc_typing = !pc_dialog && (self.inner.ui.text_edit.is_some() || ctx.text_edit_focused());''')
# Avoid flooding the live trace and obscuring the real Esc/Y/N/C transitions.
patch(host, '        if pc_received > 0 {\n            self.pc_keyboard_diag.push(format!("JNI polled: {pc_received} records (not proof of a press)"));\n        }', '')
patch(host, 'let pc_received = hardware_keys::inject(', 'hardware_keys::inject(')
# Some physical key maps represent Escape as Unicode U+001B. Preserve the
# named key through winit so the text editor receives an Escape press.
patch(args.vendor/'winit/src/platform_impl/android/keycodes.rs',
      '    let native = NativeKey::Android(keycode.into());',
      '''    if keycode == Escape {
        return Key::Named(NamedKey::Escape);
    }
    let native = NativeKey::Android(keycode.into());''')
