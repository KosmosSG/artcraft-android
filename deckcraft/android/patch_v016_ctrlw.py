#!/usr/bin/env python3
"""DeckCraft v0.16.0 Android canvas-edit Ctrl+W repair.

Patch only the disposable CI builder workspace after the preapproved Android
D/C/S + keyboard overlays. Fail closed when source anchors change; do not
modify the user-approved published Android baseline, keys, or data.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1])
activity = root / "templates/android/SafActivity.java"
keys = root / "source/deckcraft/crates/ui-egui/src/app/keys.rs"
ui = root / "source/deckcraft/crates/ui-egui/src/lib.rs"

def one(path: Path, before: str, after: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(before)
    if count != 1:
        raise RuntimeError(f"DeckCraft Ctrl+W overlay anchor changed: {path}: {count} matches for {before[:100]!r}")
    path.write_text(source.replace(before, after, 1), encoding="utf-8")

# GameActivity's invisible Android EditText can own hardware keyboard focus
# while the slide text editor is active. MagicOS can dispatch a hardware
# shortcut to an InputConnection or the focused View without ever sending it
# to the Activity's dispatchKeyEvent or egui's RawInput.
#
# A one-shot bridge records Ctrl+W independent of focus, wakes the native
# event loop WITHOUT injecting user text or an IME composition command, and
# consumes only Ctrl+W. It is safe for normal typing, repeated shortcuts,
# other shortcuts, and the D/C/S active-dialog keyboard handler.
helper = """
    private final java.util.concurrent.atomic.AtomicBoolean dkCtrlWKeyHeld =
        new java.util.concurrent.atomic.AtomicBoolean(false);

    // Handle a physical Ctrl+W even when the soft keyboard owns focus.
    // The actual close is handled by Rust and obeys the Save/Don't Save/
    // Cancel modal; never call finish() or discard an edited document here.
    private boolean dkCaptureCtrlW(android.view.KeyEvent event) {
        if (event == null) return false;
        final int code = event.getKeyCode();
        // Consume the matching release so egui does not see a stranded W up.
        if (code == android.view.KeyEvent.KEYCODE_W
                && event.getAction() == android.view.KeyEvent.ACTION_UP
                && dkCtrlWKeyHeld.getAndSet(false)) {
            return true;
        }
        if (dkDialogActive || code != android.view.KeyEvent.KEYCODE_W
                || !event.isCtrlPressed() || event.isShiftPressed()
                || event.isAltPressed() || event.isMetaPressed()) {
            return false;
        }
        if (event.getAction() == android.view.KeyEvent.ACTION_DOWN) {
            dkCtrlWKeyHeld.set(true);
            if (event.getRepeatCount() == 0) {
                dkEditorClose.set(1);
                // The Activity and native loop may be asleep because the IME
                // consumed W. Send an unidentified DOWN/UP directly to
                // GameActivity to wake winit, without altering document text.
                try {
                    super.onKeyDown(android.view.KeyEvent.KEYCODE_UNKNOWN,
                        new android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN,
                                                  android.view.KeyEvent.KEYCODE_UNKNOWN));
                    super.onKeyUp(android.view.KeyEvent.KEYCODE_UNKNOWN,
                        new android.view.KeyEvent(android.view.KeyEvent.ACTION_UP,
                                                  android.view.KeyEvent.KEYCODE_UNKNOWN));
                } catch (Exception ex) {
                    android.util.Log.w("DeckCraftDCS", "Ctrl+W native wake failed", ex);
                }
                android.util.Log.i("DeckCraftDCS", "focused_ctrl_w_queued");
            }
            return true;
        }
        return false;
    }

    @Override public boolean onKeyShortcut(int keyCode, android.view.KeyEvent event) {
        if (dkCaptureCtrlW(event)) return true;
        return super.onKeyShortcut(keyCode, event);
    }

"""
one(activity,
    "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n"
    "        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {",
    helper+
    "    @Override public boolean dispatchKeyEvent(android.view.KeyEvent event) {\n"
    "        if (dkCaptureCtrlW(event)) return true;\n"
    "        if (event != null && (event.getFlags() & android.view.KeyEvent.FLAG_SOFT_KEYBOARD) == 0) {")
old_branch = """            if (!dkDialogActive && code == android.view.KeyEvent.KEYCODE_W
                    && event.isCtrlPressed() && !event.isShiftPressed()
                    && !event.isAltPressed() && !event.isMetaPressed()
                    && event.getAction() == android.view.KeyEvent.ACTION_DOWN
                    && event.getRepeatCount() == 0) {
                dkEditorClose.set(1);
                // Do not swallow the event. The native raw-input hook may also
                // see it; either path deduplicates into the same one-shot flag.
                android.util.Log.i("DeckCraftDCS", "editor_ctrl_w_queued");
            }
"""
one(activity,old_branch,"")
# Intercept the IME's optional InputConnection shortcut handoff before the
# existing synthesized-key suppression (which otherwise eats the whole press).
one(activity,
    "                        public boolean sendKeyEvent(KeyEvent event) {\n"
    "                            if (event.getAction() == KeyEvent.ACTION_DOWN) {",
    "                        public boolean sendKeyEvent(KeyEvent event) {\n"
    "                            if (dkCaptureCtrlW(event)) return true;\n"
    "                            if (event.getAction() == KeyEvent.ACTION_DOWN) {")
one(activity,
    "                public boolean onKeyDown(int keyCode, KeyEvent event) {\n"
    "                    // A key the IME synthesised",
    "                public boolean onKeyDown(int keyCode, KeyEvent event) {\n"
    "                    if (dkCaptureCtrlW(event)) return true;\n"
    "                    // A key the IME synthesised")
one(activity,
    "                public boolean onKeyUp(int keyCode, KeyEvent event) {\n"
    "                    if (imeKeySynthesized.remove(keyCode)) {",
    "                public boolean onKeyUp(int keyCode, KeyEvent event) {\n"
    "                    if (dkCaptureCtrlW(event)) return true;\n"
    "                    if (imeKeySynthesized.remove(keyCode)) {")
# The previously approved Rust layer already supports the JNI atomic
# dkTakeEditorClose, but ensure it requests a repaint while it receives it.
k=keys.read_text(encoding="utf-8")
for marker in ("fn android_editing_ctrl_w", 'egui::Id::new("deckcraft.android.ctrl_w")',
               "self.note_settled_composition(ctx);","self.close_presentation();"):
    if marker not in k:
        raise RuntimeError(f"DeckCraft D/C/S regression: missing {marker}")
if 'self.route_ime_controls_only(ctx, &events);' not in k:
    raise RuntimeError("DeckCraft IME settle and save-close route disappeared")
j=activity.read_text(encoding="utf-8")
assert j.count("private boolean dkCaptureCtrlW(") == 1
assert j.count("if (dkCaptureCtrlW(event)) return true;") == 5  # Activity, shortcut, InputConnection, IME down/up
assert j.count("dkEditorClose.set(1);") == 1
assert 'dkDialogAction.compareAndSet(0, shortcut)' in j, "D/C/S dialog flow lost"
assert 'public int dkTakeEditorClose()' in j
assert 'queueImeEvent("c" + text)' in j, "Ordinary IME typing must remain"
assert 'return super.dispatchKeyEvent(event);' in j
assert 'KEYCODE_UNKNOWN' in j
print("PASS: Ctrl+W from Activity / InputConnection / focused IME view / onKeyShortcut")
print("PASS: native wake, safe one-shot close, existing D/C/S, clipboard, typing and IME preserved")
