"""Source-only gates for Android.11 hover wheel and Undo/Redo, on staged adapter."""
from pathlib import Path
import sys

def verify(root: Path) -> None:
    a = root / "adapters/vectorcraft"
    j = (a / "java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    h = (a / "src/lib.rs").read_text()
    m = (a / "src/android_modifiers.rs").read_text()
    w = (a / "src/stylus_wheel.rs").read_text()
    assert j.count("VC_ANDROID11_HOVER_BUTTON_EDGE") == 1
    assert j.count("VC_ANDROID11_CTRL_Z_REDO") == 1
    assert h.count("VC_ANDROID11_CTRL_SHIFT_Z") == 1
    assert 'getBoolean("enabled", true)' in j
    assert 'getSharedPreferences("vc_stylus_wheel"' in j
    assert 'vcIsMagicPencil(input)' in j and '!vcIsMagicPencil(d)' in j
    assert j.count('private boolean vcIsMagicPencil(') == 1
    assert 'vcObserveStylusHoverButton(motion);' in j
    assert j.count('vcObserveStylusHoverButton(motion);') == 2
    assert 'motion.getButtonState() & mask' in j
    assert 'motion.getToolType(0)' in j
    assert 'ACTION_HOVER_MOVE' in j and 'ACTION_BUTTON_PRESS' in j
    assert 'vcPenHoverButtonHeld = false;' in j
    assert 'vcWheelKeys.offer("S")' in j
    assert 'return super.dispatchGenericMotionEvent(motion);' in j
    assert 'event.isCtrlPressed() && !event.isAltPressed()' in j
    assert 'vcAndroid11HistoryKeys.offer(event.isShiftPressed() ? -91 : -90)' in j
    assert 'vcAndroid11HistoryMode(boolean enabled)' in j
    assert 'vcAndroid11PollHistoryShortcut()' in j
    assert 'vcAndroid11HistoryEnabled && !imeWanted && key == KeyEvent.KEYCODE_Z' in j
    assert 'if (!enabled) vcAndroid11HistoryKeys.clear();' in j
    assert h.count('vc_android11_poll_history(&self)') == 1
    assert h.count('vc_android11_set_history_enabled(&self, enabled: bool)') == 1
    assert 'let history_allowed = self.inner.session.active().is_some()' in h
    assert '!modal && !editing && !field_focused && !composing' in h
    assert 'match self.bridge.vc_android11_poll_history()' in h
    assert 'ctx.data_mut(|data|' in h
    assert 'JValue::Bool(enabled)' in h
    assert 'let command = match code {' in h
    assert '-90 => "edit.undo"' in h and '-91 => "edit.redo"' in h
    assert 'self.inner.run("edit.undo", serde_json::json!({}))' in h
    assert 'self.inner.run("edit.redo", serde_json::json!({}))' in h
    assert 'has_android_redo_chord(' in h
    assert 'consume_android_redo_chord(raw);' in h
    assert 'pub fn has_android_redo_chord(' in m
    assert 'pub fn consume_android_redo_chord(' in m
    assert 'modifiers.shift && !modifiers.alt' in m
    assert 'repeat: false' in m
    assert 'const DEFAULT_LAYOUT: [usize; 8]' in w
    # The approved Android.10 .ai typing pipeline is still present.
    assert 'vcResetIme(long requestId)' in j
    assert 'vcImeFocusEpoch' in j
    assert 'vcDocumentChanged()' in j
    assert 'self.ime.poll(ctx, raw);' in h
    assert 'get_temp::<Option<egui::ImeResetId>>(key).flatten()' in (a / "src/ime_bridge.rs").read_text()
    assert 'self.stylus_wheel.capture(ctx, raw, wheel_blocked)' in h
    print("PASS: Android.11 hover-side-button edge, opt-out setting, Ctrl+Z/Shift+Z, Android.10 IME preserved")

if __name__ == "__main__":
    verify(Path(sys.argv[1]))
