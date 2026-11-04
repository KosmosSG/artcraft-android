#!/usr/bin/env python3
"""PhotoCraft v0.19 Android.7 input fixes: copied API semantics from official
Android trackpad MotionEvent docs and menu/dialog routing from v0.19 upstream.

Always applied to disposable CI checkout after android6_ui_overlay.py.
Published stable PhotoCraft's native sources remain byte-identical.
"""
import argparse
from pathlib import Path
import subprocess

UPSTREAM="327c4cc82e737a3e0af7c147a477126d77525495"

def patch(path,old,new):
    data=path.read_text(encoding="utf-8")
    count=data.count(old)
    if count!=1: raise RuntimeError(f"Android.7 unreviewed anchor in {path}: {count}")
    path.write_text(data.replace(old,new,1),encoding="utf-8")
    print(f"Android.7 adapted: {path}")

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--upstream",type=Path,required=True)
    a.add_argument("--adapter",type=Path,required=True)
    opt=a.parse_args()
    actual=subprocess.check_output(["git","-C",str(opt.upstream),"rev-parse","HEAD"],text=True).strip()
    if actual!=UPSTREAM: raise RuntimeError(f"Unexpected upstream {actual}")
    host=opt.adapter/"src/lib.rs"
    act=opt.adapter/"java/com/artcraft/photocraft/PhotoCraftActivity.java"
    menus=opt.upstream/"crates/ui-egui/src/menus.rs"
    dialog=opt.upstream/"crates/ui-egui/src/dialogs/discard_ui.rs"

    # The reference's Pad::reserve uses this dedicated strip. Upstream UI
    # respects edge_strip and lays the panels out to the side; the previous
    # floating Area obscured the Properties panel.
    patch(host,
'''        self.inner.ui(ui, _frame);
''',
'''        self.shortcut_pad.reserve(ui);
        self.inner.ui(ui, _frame);
''')

    # The upstream discard UI consumes Key::Y/N/C from egui, but the Android
    # IME keyboard may never produce it. An explicit one-frame dialog-only
    # command queue preserves modal isolation without stealing typed text.
    patch(menus,
'''pub fn artcraft_take_pc_menu_action() -> u8 {
    ARTCRAFT_PC_MENU_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
''',
'''pub fn artcraft_take_pc_menu_action() -> u8 {
    ARTCRAFT_PC_MENU_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
static ARTCRAFT_DIALOG_KEY: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
pub fn artcraft_queue_dialog_key(key: u8) {
    ARTCRAFT_DIALOG_KEY.store(key, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "android")]
pub fn artcraft_take_dialog_key() -> u8 {
    ARTCRAFT_DIALOG_KEY.swap(0, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
pub fn artcraft_discard_active(app: &crate::PhotocraftApp) -> bool {
    app.discard.is_some()
}
''')
    patch(host,
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
''',
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
        if photocraft_ui_egui::menus::artcraft_discard_active(&self.inner) {
            // The modal owns these keys; even an IME Text("n") should
            // dismiss the modal instead of being consumed by old focus.
            for event in &raw.events {
                let key = match event {
                    egui::Event::Key { key: egui::Key::Y, pressed: true, .. } => 1,
                    egui::Event::Key { key: egui::Key::N, pressed: true, .. } => 2,
                    egui::Event::Key { key: egui::Key::C, pressed: true, .. } => 3,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("y") => 1,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("n") => 2,
                    egui::Event::Text(txt) if txt.eq_ignore_ascii_case("c") => 3,
                    _ => 0,
                };
                if key != 0 {
                    photocraft_ui_egui::menus::artcraft_queue_dialog_key(key);
                }
            }
        } else {
            // Ensure a key from an older prompt cannot answer a new one.
            let _ = photocraft_ui_egui::menus::artcraft_take_dialog_key();
        }
''')
    patch(dialog,
'''    let mut answer = ctx.input_mut(|i| buttons.iter().find(|b| b.2.is_some_and(|k| i.consume_key(egui::Modifiers::NONE, k))).map(|b| b.4));
''',
'''    let mut answer = ctx.input_mut(|i| buttons.iter().find(|b| b.2.is_some_and(|k| i.consume_key(egui::Modifiers::NONE, k))).map(|b| b.4));
    #[cfg(target_os = "android")]
    {
        let direct = match crate::menus::artcraft_take_dialog_key() {
            1 => Some(Answer::Save), 2 => Some(Answer::Discard),
            3 => Some(Answer::Cancel), _ => None,
        };
        if direct.is_some() { answer = direct; }
    }
''')

    # Android API 34+: physical touchpad 2-finger ACTION_MOVE scroll can be
    # SOURCE_MOUSE with pointerCount=1; unlike AXIS_VSCROLL, the effective
    # distance is AXIS_GESTURE_SCROLL_X/Y_DISTANCE in pixels.
    # Under Android 15 the old code completely ignored these events.
    patch(act,
'''            float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
            float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
''',
'''            float vertical = event.getAxisValue(android.view.MotionEvent.AXIS_VSCROLL);
            float horizontal = event.getAxisValue(android.view.MotionEvent.AXIS_HSCROLL);
            if (android.os.Build.VERSION.SDK_INT >= 34
                    && Math.abs(vertical) < 0.0001f && Math.abs(horizontal) < 0.0001f) {
                // Android gesture axes are in DISPLAY PIXELS, not wheel steps.
                horizontal = event.getAxisValue(
                    android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE) / 42.0f;
                vertical = -event.getAxisValue(
                    android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE) / 42.0f;
            }
''')
    # Some OEMs dispatch these trackpad axes as ACTION_MOVE, not ACTION_SCROLL.
    patch(act,
'''        return super.dispatchGenericMotionEvent(event);
''',
'''        if (android.os.Build.VERSION.SDK_INT >= 34
                && event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE) {
            float dx = event.getAxisValue(
                android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE);
            float dy = event.getAxisValue(
                android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE);
            if ((Math.abs(dx) > 0.01f || Math.abs(dy) > 0.01f)
                    && artcraftTrackpadScroll.size() < 32) {
                View decor = getWindow().getDecorView();
                artcraftTrackpadScroll.offer(dx / 42.0f + "," + (-dy / 42.0f) + ","
                    + event.getX() + "," + event.getY() + ","
                    + decor.getWidth() + "," + decor.getHeight());
            }
        }
        return super.dispatchGenericMotionEvent(event);
''')

    # Android.8 HOTKEY REGRESSION: include all officially supported Photoshop
    # tool shortcut letters. Android.7 only forwarded V/T/B/Y/N/C and skipped
    # M (Rectangular Marquee) and most of the other toolbar bindings.
    # Preserve original event dispatch and never read or log typed text.
    hardware = opt.adapter/"src/hardware_keys.rs"
    patch(hardware,
'''fn mapped_key(code: u32) -> Option<egui::Key> {
    Some(match code {
        111 => egui::Key::Escape, // Android KEYCODE_ESCAPE
        50 => egui::Key::V,
        48 => egui::Key::T,
        30 => egui::Key::B,
        53 => egui::Key::Y,
        42 => egui::Key::N,
        31 => egui::Key::C,
        51 => egui::Key::W,
        32 => egui::Key::D,
        47 => egui::Key::S,
        66 => egui::Key::Enter,
        _ => return None,
    })
}
''',
'''fn mapped_key(code: u32) -> Option<egui::Key> {
    // Android KeyEvent KEYCODE_A..KEYCODE_Z are consecutive (29..=54).
    // Forward only key identity; Android-owned text / IME content stays private.
    Some(match code {
        29 => egui::Key::A, 30 => egui::Key::B,
        31 => egui::Key::C, 32 => egui::Key::D,
        33 => egui::Key::E, 34 => egui::Key::F,
        35 => egui::Key::G, 36 => egui::Key::H,
        37 => egui::Key::I, 38 => egui::Key::J,
        39 => egui::Key::K, 40 => egui::Key::L,
        41 => egui::Key::M, 42 => egui::Key::N,
        43 => egui::Key::O, 44 => egui::Key::P,
        45 => egui::Key::Q, 46 => egui::Key::R,
        47 => egui::Key::S, 48 => egui::Key::T,
        49 => egui::Key::U, 50 => egui::Key::V,
        51 => egui::Key::W, 52 => egui::Key::X,
        53 => egui::Key::Y, 54 => egui::Key::Z,
        66 => egui::Key::Enter,
        111 => egui::Key::Escape,
        _ => return None,
    })
}
''')

    # An OEM keyboard may deliver letter input as Text only. Do not turn
    # letters into tools inside a text field; a modal discard prompt is the
    # exception, and only its three explicit answers are eligible there.
    patch(hardware,
'''    raw: &mut egui::RawInput, ctx: &egui::Context, inline_text_edit: bool,
) {
    if inline_text_edit || ctx.text_edit_focused() { return; }
''',
'''    raw: &mut egui::RawInput, ctx: &egui::Context, inline_text_edit: bool,
    discard_prompt_active: bool,
) {
    if !discard_prompt_active && (inline_text_edit || ctx.text_edit_focused()) {
        return;
    }
''')
    patch(hardware,
'''        let key = match text.as_str().to_ascii_lowercase().as_str() {
            "v" => egui::Key::V, "t" => egui::Key::T,
            "b" => egui::Key::B, "y" => egui::Key::Y,
            "n" => egui::Key::N, "c" => egui::Key::C,
            "d" => egui::Key::D, "s" => egui::Key::S,
            _ => continue,
        };
''',
'''        let key = match text.as_str().to_ascii_lowercase().as_str() {
            "a" => egui::Key::A, "b" => egui::Key::B,
            "c" => egui::Key::C, "d" => egui::Key::D,
            "e" => egui::Key::E, "g" => egui::Key::G,
            "h" => egui::Key::H, "i" => egui::Key::I,
            "j" => egui::Key::J, "k" => egui::Key::K,
            "l" => egui::Key::L, "m" => egui::Key::M,
            "n" => egui::Key::N, "o" => egui::Key::O,
            "p" => egui::Key::P, "r" => egui::Key::R,
            "s" => egui::Key::S, "t" => egui::Key::T,
            "u" => egui::Key::U, "v" => egui::Key::V,
            "w" => egui::Key::W, "y" => egui::Key::Y,
            "z" => egui::Key::Z,
            _ => continue,
        };
        if discard_prompt_active && !matches!(key, egui::Key::Y | egui::Key::N | egui::Key::C) {
            continue;
        }
''')
    patch(host,
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
        );
''',
'''        hardware_keys::recover_text_keys(
            raw, ctx, self.inner.ui.text_edit.is_some(),
            photocraft_ui_egui::menus::artcraft_discard_active(&self.inner),
        );
''')

    # Extend the pre-existing, verified direct tool-command fallback. The
    # upstream shortcut handler still owns custom remaps and Shift cycling.
    # Do not select a tool while a modal dialog or inline editor owns focus.
    patch(host,
'''                if !modifiers.ctrl && !modifiers.alt && !modifiers.shift
                    && self.inner.ui.text_edit.is_none() {
                    self.artcraft_tool_pending = match key {
                        egui::Key::V => Some("tools.select.move"),
                        egui::Key::T => Some("tools.select.type"),
                        egui::Key::B => Some("tools.select.brush"),
                        _ => self.artcraft_tool_pending,
                    };
                }
''',
'''                if !modifiers.ctrl && !modifiers.alt && !modifiers.shift
                    && self.inner.ui.text_edit.is_none()
                    && !ctx.text_edit_focused()
                    && !photocraft_ui_egui::menus::artcraft_discard_active(&self.inner) {
                    self.artcraft_tool_pending = match key {
                        egui::Key::V => Some("tools.select.move"),
                        egui::Key::M => Some("tools.select.rectMarquee"),
                        egui::Key::L => Some("tools.select.lasso"),
                        egui::Key::W => Some("tools.select.magicWand"),
                        egui::Key::C => Some("tools.select.crop"),
                        egui::Key::I => Some("tools.select.eyedropper"),
                        egui::Key::B => Some("tools.select.brush"),
                        egui::Key::E => Some("tools.select.eraser"),
                        egui::Key::G => Some("tools.select.gradient"),
                        egui::Key::T => Some("tools.select.type"),
                        egui::Key::H => Some("tools.select.hand"),
                        egui::Key::R => Some("tools.select.rotateView"),
                        egui::Key::Z => Some("tools.select.zoom"),
                        egui::Key::J => Some("tools.select.spotHealing"),
                        egui::Key::S => Some("tools.select.cloneStamp"),
                        egui::Key::Y => Some("tools.select.historyBrush"),
                        egui::Key::O => Some("tools.select.dodge"),
                        egui::Key::P => Some("tools.select.pen"),
                        egui::Key::A => Some("tools.select.pathSelection"),
                        egui::Key::U => Some("tools.select.rectangle"),
                        egui::Key::K => Some("tools.select.frame"),
                        _ => self.artcraft_tool_pending,
                    };
                }
''')

    # The Android activity filters physical key codes, not typed strings. It
    # must match Rust's full allowlist and capture OEM pre-IME key delivery
    # without consuming the native key event or its editing behavior.
    patch(act,
'''        if (code != KeyEvent.KEYCODE_ESCAPE && code != KeyEvent.KEYCODE_V
                && code != KeyEvent.KEYCODE_T && code != KeyEvent.KEYCODE_B
                && code != KeyEvent.KEYCODE_Y && code != KeyEvent.KEYCODE_N
                && code != KeyEvent.KEYCODE_C && code != KeyEvent.KEYCODE_W
                && code != KeyEvent.KEYCODE_D && code != KeyEvent.KEYCODE_S
                && code != KeyEvent.KEYCODE_ENTER) return;
''',
'''        if ((code < KeyEvent.KEYCODE_A || code > KeyEvent.KEYCODE_Z)
                && code != KeyEvent.KEYCODE_ESCAPE
                && code != KeyEvent.KEYCODE_ENTER) return;
''')
    patch(act,
'''                @Override
                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    pcRememberHardwareKey(event);
''',
'''                @Override
                public boolean onKeyPreIme(int keyCode, KeyEvent event) {
                    // Some tablet IMEs intercept Y/N/C and tool letters before
                    // Activity.dispatchKeyEvent. This records the original
                    // key once and leaves the Android IME lifecycle untouched.
                    pcRememberHardwareKey(event);
                    return super.onKeyPreIme(keyCode, event);
                }

                @Override
                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    pcRememberHardwareKey(event);
''')
    patch(act,
'''    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
''',
'''    @Override
    public boolean dispatchKeyShortcutEvent(KeyEvent event) {
        // Preserve Ctrl shortcuts even when an OEM routes them separately.
        pcRememberHardwareKey(event);
        return super.dispatchKeyShortcutEvent(event);
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
''')
    # All direct/Java injection hooks must be present before the costly build.
    assert "egui::Key::M => Some(\"tools.select.rectMarquee\")" in host.read_text()
    assert "discard_prompt_active" in hardware.read_text()
    assert "onKeyPreIme" in act.read_text()
    assert "dispatchKeyShortcutEvent" in act.read_text()
    # Android.9: the hidden Java EditText must stop owning the PHYSICAL keyboard
    # after the upstream Type session is committed. On some tablet/Gboard
    # configurations, a stale IME view keeps taking M/V/T/B and Y/N/C even
    # though the canvas is no longer in Type edit mode. Do not release another
    # egui text field's focus, and NEVER commit or discard document contents.
    patch(host,
'''    artcraft_tool_pending: Option<&'static str>,
''',
'''    artcraft_tool_pending: Option<&'static str>,
    artcraft_type_ime_was_active: bool,
''')
    patch(host,
'''                artcraft_tool_pending: None,
''',
'''                artcraft_tool_pending: None,
                artcraft_type_ime_was_active: false,
''')
    patch(host,
'''        self.inner.logic(ctx, frame);
''',
'''        self.inner.logic(ctx, frame);
        // The custom Type layer keeps its text in the document, not in the
        // invisible EditText. Once editing has ended, release Android IME focus
        // so the next physical tool key can reach NativeActivity again.
        // Do not dismiss an unrelated currently focused egui input widget.
        if self.artcraft_type_ime_was_active
            && self.inner.ui.text_edit.is_none()
            && !ctx.text_edit_focused()
        {
            if let Err(error) = self.bridge.hide_native_keyboard() {
                log::warn!("PhotoCraft type editor IME focus release: {error}");
            }
        }
        self.artcraft_type_ime_was_active = self.inner.ui.text_edit.is_some();
''')
    patch(host,
'''    fn show_native_keyboard(&self) -> Result<(), String> {
''',
'''    fn hide_native_keyboard(&self) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, jni_str!("imeHide"), jni_sig!("()V"), &[])?;
            Ok(())
        }).map_err(|e| e.to_string())
    }

    fn show_native_keyboard(&self) -> Result<(), String> {
''')

    # A hide runnable queued just before a new text editor opens must not
    # dismiss that NEW editor's keyboard (Gboard may schedule view actions).
    patch(act,
'''    public void imeHide() {
        imeWanted = false;
        final EditText view = imeView;
        if (view == null) {
            return;
        }
        runOnUiThread(() -> {
            try {
''',
'''    public void imeHide() {
        imeWanted = false;
        final EditText view = imeView;
        if (view == null) {
            return;
        }
        runOnUiThread(() -> {
            if (imeWanted) return; // A newer imeShow() superseded this hide.
            try {
''')

    assert "artcraft_type_ime_was_active" in host.read_text()
    assert 'jni_str!("imeHide")' in host.read_text()
    assert "A newer imeShow() superseded this hide." in act.read_text()
    print("Android.9: release hidden Gboard EditText focus on Type-mode exit; preserve active UI text inputs")

    print("Android.8: full tool-letter physical shortcuts and Y/N/C modal pre-IME routing staged")

    print("Android.7: dedicated Shortcut Pad strip, Android 14+ gesture axes and modal dialog hotkeys staged")

if __name__=="__main__":
    main()
