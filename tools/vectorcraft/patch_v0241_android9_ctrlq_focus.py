"""Android.9: repair stale physical-key focus after Ctrl+Q/relaunch.

The previous hardware text bridge only runs in the hidden EditText's onKeyDown.
If NativeActivity retains a stale focus target after a normal exit, printable
keys may never reach that handler. Repair focus on resume and provide a guarded
Activity-dispatch fallback while the native Type tool requests IME focus.
"""
from pathlib import Path
import sys

def once(s, a, b):
    if s.count(a) != 1:
        raise RuntimeError(f"Android.9 anchor count {s.count(a)}: {a[:80]}")
    return s.replace(a, b, 1)

def patch(root):
    p = Path(root) / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    s = p.read_text()
    anchor = "    /** Show the soft keyboard by focusing the IME host view. Called by the Rust shell via JNI. */"
    lifecycle = """    // A normal Ctrl+Q exit can leave the process/Activity focus tree alive.
    // Restore the native surface when not typing; do not activate an IME on resume.
    @Override
    protected void onResume() {
        super.onResume();
        getWindow().getDecorView().post(() -> {
            if (!imeWanted) {
                final View container = getWindow().getDecorView()
                        .findViewById(android.R.id.content);
                final SurfaceView surface = container == null ? null : findNativeSurface(container);
                if (surface != null && surface.isShown()) {
                    surface.setFocusable(true);
                    surface.setFocusableInTouchMode(true);
                    surface.requestFocus();
                }
            } else if (imeView != null && !imeView.hasFocus()) {
                imeView.requestFocus();
                final InputMethodManager imm =
                        (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
                if (imm != null) imm.restartInput(imeView);
            }
            Log.i(TAG, "VC_ANDROID9 resume imeWanted=" + imeWanted
                    + " imeFocused=" + (imeView != null && imeView.hasFocus()));
        });
    }

    // Activity-level safety net: when a physical keyboard reaches Activity
    // dispatch but the IME host has lost focus, do not silently drop text.
    // The normal focused EditText path still owns text to avoid duplicates.
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event != null && event.getAction() == KeyEvent.ACTION_DOWN
                && imeWanted && imeView != null && !imeView.hasFocus()
                && event.getDeviceId() >= 0 && !event.isSystem()
                && !event.isCtrlPressed() && !event.isAltPressed()
                && !event.isMetaPressed() && event.getKeyCode() != KeyEvent.KEYCODE_ENTER) {
            int unicode = event.getUnicodeChar(event.getMetaState());
            if (unicode >= 0x20 && Character.isValidCodePoint(unicode)
                    && !Character.isISOControl(unicode)) {
                imeEvents.offer("t" + new String(Character.toChars(unicode)));
                vcWakeNativeLoop();
                Log.i(TAG, "VC_ANDROID9 dispatch_recovered_physical_key");
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

"""
    # Android.8 instrumentation already adds dispatchKeyEvent; insert fallback
    # into its existing method instead of adding a duplicate override.
    if "    public boolean dispatchKeyEvent(KeyEvent event) {" in s:
        s = once(s, "    public boolean dispatchKeyEvent(KeyEvent event) {",
            "    public boolean dispatchKeyEvent(KeyEvent event) {\n"
            "        if (event != null && event.getAction() == KeyEvent.ACTION_DOWN\n"
            "                && imeWanted && imeView != null && !imeView.hasFocus()\n"
            "                && event.getDeviceId() >= 0 && !event.isSystem()\n"
            "                && !event.isCtrlPressed() && !event.isAltPressed()\n"
            "                && !event.isMetaPressed() && event.getKeyCode() != KeyEvent.KEYCODE_ENTER) {\n"
            "            int unicode = event.getUnicodeChar(event.getMetaState());\n"
            "            if (unicode >= 0x20 && Character.isValidCodePoint(unicode)\n"
            "                    && !Character.isISOControl(unicode)) {\n"
            "                imeEvents.offer(\"t\" + new String(Character.toChars(unicode)));\n"
            "                vcWakeNativeLoop();\n"
            "                Log.i(TAG, \"VC_ANDROID9 dispatch_recovered_physical_key\");\n"
            "                return true;\n"
            "            }\n"
            "        }")
        lifecycle = lifecycle[:lifecycle.index("    // Activity-level safety net:")]
    s = once(s, anchor, lifecycle + anchor)
    # Whenever native Type editing starts, rebuild the host's input connection
    # if the prior Activity session left it stale.
    s = once(s, "                view.requestFocus();\n                InputMethodManager imm =",
        "                view.requestFocus();\n                InputMethodManager imm =")
    p.write_text(s)
    print("PASS: Android.9 resume focus repair and guarded dispatch recovery")

if __name__ == "__main__":
    patch(Path(sys.argv[1]))
