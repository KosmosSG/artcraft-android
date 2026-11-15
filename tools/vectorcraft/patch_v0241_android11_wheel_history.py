"""VectorCraft Android.11: enable opt-out wheel, pen hover-button edge, Ctrl+Z/Redo.

Apply after Android.10 verified IME transport and all earlier Java/Rust overlays,
on disposable builder staging only. Preserve .ai IME reset, document lifetime,
trackpad/pan, native pen motion, published signing and existing wheel layout.
"""
from pathlib import Path
import sys

def once(s: str, old: str, new: str, label: str) -> str:
    n = s.count(old)
    if n != 1:
        raise ValueError(f"Android.11 {label}: expected one reviewed anchor, got {n}")
    return s.replace(old, new, 1)

def patch(root: Path) -> None:
    a = root / "adapters/vectorcraft"
    java = a / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    host = a / "src/lib.rs"
    modifiers = a / "src/android_modifiers.rs"
    wheel = a / "src/stylus_wheel.rs"
    j = java.read_text()
    h = host.read_text()
    m = modifiers.read_text()
    w = wheel.read_text()
    if "VC_ANDROID11_HOVER_BUTTON_EDGE" in j or "VC_ANDROID11_CTRL_SHIFT_Z" in h:
        raise RuntimeError("Android.11 wheel/history patch already applied")

    # Freshly installed separate test candidates otherwise start with the
    # wheel OFF, even though the user has an enabled wheel in their published
    # app: SharedPreferences are intentionally isolated by applicationId.
    # Respect an explicitly saved OFF switch and all saved 8-slot settings.
    j = once(j,
        'getBoolean("enabled", false);',
        'getBoolean("enabled", true);',
        "new candidate stylus wheel default")
    j = once(j,
        '    private SurfaceView vcPenHoverSurface = null;',
        '''    private SurfaceView vcPenHoverSurface = null;
    private boolean vcPenHoverButtonHeld = false;''',
        "hover edge state")
    # Pen input names can have HONOR prefix or spaces. Never treat an
    # ordinary external keyboard as a stylus.
    j = once(j,
        'input.getName() != null && input.getName().contains("Magic-Pencil 4s")',
        'vcIsMagicPencil(input)',
        "native stylus allowed-device IDs")
    j = once(j,
        'd.getName() == null || !d.getName().contains("Magic-Pencil 4s")',
        '!vcIsMagicPencil(d)',
        "Java stylus button device identity")
    j = once(j,
        '    private boolean vcStylusIntercept(KeyEvent event) {',
        '''    private boolean vcIsMagicPencil(android.view.InputDevice device) {
        if (device == null || device.getName() == null) return false;
        final String name = device.getName().toLowerCase(java.util.Locale.ROOT);
        return name.contains("magic-pencil") || name.contains("magic pencil")
            || name.contains("magicpencil");
    }
    private boolean vcStylusIntercept(KeyEvent event) {''',
        "pen-only identifier")
    # Some HONOR pens send side-button state in MotionEvent while hovering,
    # rather than a DPAD key. Listen for a true 0->1 button edge only during
    # real tool-type STYLUS/ERASER hover; never generate keys from contact,
    # fingers, mouse or a trackpad. The listener returns false so native winit
    # still receives every hover/motion packet.
    j = once(j,
        '    // This passive listener does NOT consume hover: winit receives the normal',
        '''    // VC_ANDROID11_HOVER_BUTTON_EDGE
    private void vcObserveStylusHoverButton(android.view.MotionEvent motion) {
        if (!vcWheelEnabled || motion.getPointerCount() < 1) {
            vcPenHoverButtonHeld = false;
            return;
        }
        final int type = motion.getToolType(0);
        if (type != android.view.MotionEvent.TOOL_TYPE_STYLUS
                && type != android.view.MotionEvent.TOOL_TYPE_ERASER) {
            vcPenHoverButtonHeld = false;
            return;
        }
        final int mask = android.view.MotionEvent.BUTTON_STYLUS_PRIMARY
                       | android.view.MotionEvent.BUTTON_STYLUS_SECONDARY;
        final boolean pressed = (motion.getButtonState() & mask) != 0;
        if (pressed && !vcPenHoverButtonHeld && vcWheelKeys.size() < 12) {
            vcWheelKeys.offer("S");
            vcWakeNativeLoop();
        }
        vcPenHoverButtonHeld = pressed;
    }

    @Override
    public boolean dispatchGenericMotionEvent(android.view.MotionEvent motion) {
        // Some Android drivers report a button transition without a HOVER_MOVE.
        // Treat it only if a recent stylus hover was observed. Never consume
        // events: NativeActivity must retain pointer and pen pressure handling.
        final int action = motion.getActionMasked();
        if ((action == android.view.MotionEvent.ACTION_BUTTON_PRESS
                || action == android.view.MotionEvent.ACTION_BUTTON_RELEASE)
                && vcStylusHoverActive()) {
            vcObserveStylusHoverButton(motion);
        }
        return super.dispatchGenericMotionEvent(motion);
    }

    // This passive listener does NOT consume hover: winit receives the normal''',
        "passive stylus-button edge helper")
    j = once(j,
        '''                    vcPenHoverVisible = true;
                    vcPenHoverAtMs = android.os.SystemClock.uptimeMillis();
                } else if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
                    vcPenHoverVisible = false;''',
        '''                    vcPenHoverVisible = true;
                    vcPenHoverAtMs = android.os.SystemClock.uptimeMillis();
                    vcObserveStylusHoverButton(motion);
                } else if (action == android.view.MotionEvent.ACTION_HOVER_EXIT) {
                    vcPenHoverVisible = false;
                    vcPenHoverButtonHeld = false;''',
        "hover-button edge (no contact required)")
    # Surface may have been replaced after the Android file picker.
    j = once(j,
        '''            vcPenHoverSurface = null;
            vcPenHoverVisible = false;
            vcInstallPenHoverListener();''',
        '''            vcPenHoverSurface = null;
            vcPenHoverVisible = false;
            vcPenHoverButtonHeld = false;
            vcInstallPenHoverListener();''',
        "rebound stylus surface")

    # MagicOS sometimes routes Ctrl+Z through Activity without a native egui
    # shortcut receipt. In the unambiguous canvas shortcut mode, Java owns
    # both DOWN and UP, sends exactly one coded action on the first DOWN,
    # and wakes Rust. Native egui fallback remains active when Java does not
    # receive the event, including inside a live Type editor.
    j = once(j,
        '''        final int mode = hardwareShortcutMode;
        final boolean plain =''',
        '''        final int mode = hardwareShortcutMode;
        // VC_ANDROID11_CTRL_Z_REDO: scoped to idle editor canvas.
        if (mode == 1 && !imeWanted && key == KeyEvent.KEYCODE_Z
                && event.isCtrlPressed() && !event.isAltPressed()
                && !event.isMetaPressed()) {
            if (event.getAction() == KeyEvent.ACTION_DOWN
                    && event.getRepeatCount() == 0
                    && physicalShortcutKeys.size() < 32) {
                physicalShortcutKeys.offer(event.isShiftPressed() ? -91 : -90);
                vcWakeNativeLoop();
            }
            return true;
        }
        final boolean plain =''',
        "physical Ctrl+Z / Ctrl+Shift+Z Java receipt")

    # Redo uses the SAME document undo history and guard as Ctrl+Z.
    marker = '''pub fn consume_android_undo_chord(raw: &mut egui::RawInput) {
    raw.events.retain(|event| !matches!(event,
        egui::Event::Key {
            key: egui::Key::Z, pressed: true, modifiers, ..
        } if (modifiers.ctrl || modifiers.command) && !modifiers.alt && !modifiers.shift
    ));
}'''
    add = '''
/// Android.11: direct Redo with Ctrl+Shift+Z, same document/IME guards as Undo.
pub fn has_android_redo_chord(
    raw: &egui::RawInput, type_editing: bool, field_focused: bool,
    composing: bool, modal_open: bool, has_document: bool,
) -> bool {
    if !has_document || modal_open || composing || (field_focused && !type_editing) {
        return false;
    }
    raw.events.iter().any(|event| matches!(event,
        egui::Event::Key {
            key: egui::Key::Z, pressed: true, repeat: false, modifiers, ..
        } if (modifiers.ctrl || modifiers.command) && modifiers.shift && !modifiers.alt
    ))
}

pub fn consume_android_redo_chord(raw: &mut egui::RawInput) {
    raw.events.retain(|event| !matches!(event,
        egui::Event::Key {
            key: egui::Key::Z, pressed: true, modifiers, ..
        } if (modifiers.ctrl || modifiers.command) && modifiers.shift && !modifiers.alt
    ));
}'''
    m = once(m, marker, marker + add, "native Redo chord guard")
    h = once(h,
        'has_android_undo_chord, consume_android_undo_chord',
        'has_android_undo_chord, consume_android_undo_chord, has_android_redo_chord, consume_android_redo_chord',
        "import history helpers")
    h = once(h,
        '''        // Treat Ctrl+Q as a native application quit request (not merely a''',
        '''        // VC_ANDROID11_CTRL_SHIFT_Z: direct Redo mirrors the Android
        // document Undo path, never reroutes IME composition or modal keys.
        if has_android_redo_chord(
            raw, editing, field_focused, composing, modal,
            self.inner.session.active().is_some(),
        ) {
            match self.inner.run("edit.redo", serde_json::json!({})) {
                Ok(_) => {
                    consume_android_redo_chord(raw);
                    ctx.request_repaint();
                }
                Err(error) => log::warn!("VectorCraft Ctrl+Shift+Z redo failed: {error}"),
            }
        }
        // Treat Ctrl+Q as a native application quit request (not merely a''',
        "native Redo engine dispatch")
    h = once(h,
        '''            let key = match (code, hardware_mode) {''',
        '''            // Java-only physical chord receipt: never send a fake
            // Ctrl+Z to egui (which could execute history twice). Run the
            // same document command, one per accepted key-down.
            if hardware_mode == 1 && (code == -90 || code == -91) {
                let command = if code == -91 { "edit.redo" } else { "edit.undo" };
                match self.inner.run(command, serde_json::json!({})) {
                    Ok(_) => ctx.request_repaint(),
                    Err(error) => log::warn!("VectorCraft Android history {command}: {error}"),
                }
                continue;
            }
            let key = match (code, hardware_mode) {''',
        "hardware Java-to-Rust undo redo delivery")
    for expected in (
        'pub fn has_android_redo_chord(', 'pub fn consume_android_redo_chord(',
    ):
        assert expected in m
    assert 'VC_ANDROID11_HOVER_BUTTON_EDGE' in j
    assert 'VC_ANDROID11_CTRL_Z_REDO' in j
    assert 'VC_ANDROID11_CTRL_SHIFT_Z' in h
    assert 'getBoolean("enabled", true)' in j
    assert 'self.inner.run("edit.redo"' in h
    assert 'self.inner.run("edit.undo"' in h
    assert 'vcResetIme(long requestId)' in j  # Android.10 IME transport retained
    assert 'self.ime.poll(ctx, raw);' in h
    assert 'self.stylus_wheel.capture(ctx, raw, wheel_blocked);' in h
    assert 'const DEFAULT_LAYOUT: [usize; 8]' in w
    java.write_text(j)
    host.write_text(h)
    modifiers.write_text(m)
    print("PASS: Android.11 opt-out wheel, hover pen button edge, and physical Undo/Redo staged; IME untouched")

if __name__ == "__main__":
    patch(Path(sys.argv[1]))
