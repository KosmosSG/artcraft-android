"""Android.7: explicit physical keyboard text delivery while Android IME owns focus.

MagicOS may send physical printable keys to the focused hidden EditText instead
of winit. Route these KEY_DOWN events through the existing ordered IME commit
queue, while preserving prior wheel-button interception and shortcut routing.
This candidate requires verification on HONOR MagicPad 4 before it can be called
a typing fix. No changes to editor reset IDs, focus epochs or document state.
"""
from pathlib import Path
import sys


def patch(root: Path) -> None:
    java = Path(root) / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    source = java.read_text()
    start = source.index("    private void imeSetup() {")
    stop = source.index("    /** Show the soft keyboard", start)
    section = source[start:stop]

    # Do not match a frozen copy of the entire handler: the Android.8 stylus
    # patch and other reviewed overlays may add guards before the fallback.
    # Anchor ONLY the anonymous IME-host onKeyDown, retaining all earlier code.
    signature = "                public boolean onKeyDown(int keyCode, KeyEvent event) {"
    next_handler = "                @Override\n                public boolean onKeyUp(int keyCode, KeyEvent event) {"
    if section.count(signature) != 1 or section.count(next_handler) != 1:
        raise RuntimeError("Android.7 IME host keyboard method changed; refusing patch")
    begin = section.index(signature)
    end = section.index(next_handler, begin)
    method = section[begin:end]
    stylus = "if (vcStylusIntercept(event)) return true;"
    fallback = "                    return false;"
    if (method.count(stylus) != 1 or method.count(fallback) != 1
            or "VC_IME7 physical_text_commit" in method):
        # Make incompatible changes visible in CI without accepting unknown code.
        raise RuntimeError("Android.7 post-stylus keyboard fallback changed; refusing patch")

    physical_text = """                    // Android.7: preserve the stylus interceptor above and
                    // enqueue only unmodified, printable physical KEY_DOWN text.
                    // The focused EditText otherwise swallows these keys on
                    // MagicOS. Do not consume shortcuts or soft IME composition.
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
"""
    method = method.replace(fallback, physical_text + fallback, 1)
    source = source[:start] + section[:begin] + method + section[end:] + source[stop:]

    # Strict source guards: keep the existing IME InputConnection commit route,
    # physical shortcut dispatch and outstanding reset/focus generations.
    assert 'imeEvents.offer("c" + text);' in source
    assert "vcImeFocusEpoch" in source
    assert source.count("VC_IME7 physical_text_commit") == 1
    assert method.index(stylus) < method.index("VC_IME7 physical_text_commit")
    assert method.count(fallback) == 1
    java.write_text(source)
    print("PASS: Android.7 physical typing queued after stylus hook; shortcut/IME fences preserved")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
