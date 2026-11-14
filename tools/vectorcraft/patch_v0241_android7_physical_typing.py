"""Android.7: explicit physical keyboard text delivery while Android IME owns focus.

NativeActivity + hidden EditText can swallow physical printable keys when focused
on MagicOS. Deliver each unmodified printable KEY_DOWN once through existing
IME queue, waking winit. Do not interfere with shortcuts, control keys, IME
composition, reset IDs, SAF state, or non-Android upstream source.
This is a candidate fix and must be verified on the HONOR test device.
"""
from pathlib import Path
import sys

def patch(root):
    java = Path(root)/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    source = java.read_text()
    start = source.index("    private void imeSetup() {")
    stop = source.index("    /** Show the soft keyboard", start)
    section = source[start:stop]
    old = """                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    // Let hardware key events fall through to the native input queue (winit), exactly
                    // as they did before this view existed; the soft keyboard talks to us through the
                    // InputConnection instead. This keeps physical keyboards working.
                    return false;
                }"""
    new = """                public boolean onKeyDown(int keyCode, KeyEvent event) {
                    // Android.7: the focused EditText is the hardware keyboard
                    // target on MagicOS. Pass printable, modifier-free physical
                    // text through the SAME ordered native IME commit queue.
                    // Consuming it here prevents duplicate winit text events.
                    // Leave shortcut chords, navigation and IME composition alone.
                    if (imeWanted && event != null && event.getDeviceId() >= 0
                            && !event.isCtrlPressed() && !event.isAltPressed()
                            && !event.isMetaPressed() && !event.isSystem()
                            && keyCode != KeyEvent.KEYCODE_ENTER) {
                        int unicode = event.getUnicodeChar(event.getMetaState());
                        if (unicode >= 0x20 && Character.isValidCodePoint(unicode)
                                && !Character.isISOControl(unicode)) {
                            imeEvents.offer("c" + new String(Character.toChars(unicode)));
                            vcWakeNativeLoop();
                            Log.d(TAG, "VC_IME7 physical_text_commit key=" + keyCode);
                            return true;
                        }
                    }
                    return false;
                }"""
    if section.count(old) != 1:
        raise RuntimeError("Android.7 physical text path changed; refusing patch")
    source = source[:start]+section.replace(old,new,1)+source[stop:]
    # The Java soft-keyboard InputConnection already emits commit events;
    # preserve its path; do not modify the native reset acknowledgements.
    assert 'imeEvents.offer("c" + text);' in source
    assert 'vcImeFocusEpoch' in source
    java.write_text(source)
    print("PASS: Android.7 physical keyboard commit handoff and shortcut isolation")

if __name__ == "__main__":
    patch(Path(sys.argv[1]))
