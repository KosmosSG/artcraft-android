from pathlib import Path
import sys
root = Path(sys.argv[1])
lib = root / 'src/lib.rs'
native = root / 'src/native_activity/mod.rs'
s = lib.read_text()
if 'pub fn pdf_stylus_configure' not in s:
    lib.write_text(s + "\n" + Path(__file__).with_name('stylus_native.rs').read_text())
s = native.read_text()
anchor = '            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {'
if 'crate::pdf_stylus_native_capture' not in s:
    assert s.count(anchor) == 1
    s = s.replace(anchor, """
            if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                let raw = key.ptr().as_ptr();
                let id = unsafe { ndk_sys::AInputEvent_getDeviceId(raw) };
                let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(raw) };
                let action = unsafe { ndk_sys::AKeyEvent_getAction(raw) };
                let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(raw) };
                if crate::pdf_stylus_native_capture(id, code, action, repeat) {
                    queue.finish_event(ndk_event, true);
                    return true;
                }
            }
""" + anchor, 1)
    native.write_text(s)
