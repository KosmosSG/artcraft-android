#!/usr/bin/env python3
"""DesignCraft TEST-only native Magic-Pencil 4s button capture.

The existing Java dispatchKeyEvent receives keyboard input but often misses
MagicOS stylus DPAD events delivered directly to NativeActivity AInputQueue.
Apply PhotoCraft's validated *device-whitelisted* native path to the private
vendored android-activity crate; never affect other ArtCraft applications.
"""
from pathlib import Path
import sys

NATIVE_BRIDGE = r"""
// DesignCraft isolated stylus input routing, based on owner-tested PhotoCraft.
#[cfg(feature = "native-activity")]
struct DcWheelNativeState {
    enabled: bool,
    allowed_ids: Vec<i32>,
    events: Vec<u8>,
    last_press: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static DC_WHEEL_NATIVE: std::sync::Mutex<DcWheelNativeState> =
    std::sync::Mutex::new(DcWheelNativeState {
        enabled: false, allowed_ids: Vec::new(), events: Vec::new(),
        last_press: None
    });

#[cfg(feature = "native-activity")]
pub fn dc_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut s) = DC_WHEEL_NATIVE.lock() {
        let verified: Vec<i32> = ids.iter().copied().take(16).filter(|id| *id > 0).collect();
        if s.enabled != enabled || s.allowed_ids != verified {
            s.events.clear();
            s.last_press = None;
        }
        s.enabled = enabled;
        s.allowed_ids = verified;
    }
}
#[cfg(feature = "native-activity")]
pub fn dc_stylus_native_capture(device: i32, code: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = DC_WHEEL_NATIVE.lock() else { return false; };
    // Native keyboard arrows stay untouched, including ComboBox navigation.
    if !state.enabled || !state.allowed_ids.contains(&device) ||
        (code != 19 && code != 20) { return false; }
    // Consume both DOWN and UP to prevent the pen from scrolling the canvas,
    // but send one signal only when the first UP completes.
    if action == 1 && repeat == 0 {
        let now = std::time::Instant::now();
        if state.last_press.is_none_or(|last|
            now.duration_since(last) >= std::time::Duration::from_millis(450)
        ) && state.events.len() < 16 {
            state.events.push(code as u8);
            state.last_press = Some(now);
            log::info!("DcStylusWheel: verified native pen device={device} code={code}");
        }
    }
    true
}
#[cfg(feature = "native-activity")]
pub fn dc_stylus_native_take() -> Vec<u8> {
    DC_WHEEL_NATIVE.lock()
        .map(|mut state| std::mem::take(&mut state.events))
        .unwrap_or_default()
}
"""

def once(path: Path, old: str, new: str, what: str):
    source = path.read_text(encoding="utf-8")
    n = source.count(old)
    if n != 1:
        raise RuntimeError(f"{what}: expected exactly 1 anchor in {path}, found {n}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

def main(root: Path):
    root = root.resolve()
    if "designcraft-builder" not in str(root):
        raise RuntimeError("Only a disposable DesignCraft build may stage native stylus")
    vendor = root / "source/designcraft/vendor/android-activity"
    lib = vendor / "src/lib.rs"
    native = vendor / "src/native_activity/mod.rs"
    if not lib.is_file() or not native.is_file():
        raise RuntimeError("NativeActivity vendor not staged")
    if "dc_stylus_configure" in lib.read_text():
        raise RuntimeError("Duplicate native wheel capture")
    with lib.open("a", encoding="utf-8") as output:
        output.write(NATIVE_BRIDGE)
    once(native,
        "            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {",
        """            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {
                // Only HONOR Magic-Pencil input IDs confirmed by Java.
                // Consume once before winit/IME converts its DPAD rocker.
                if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                    let raw = key.ptr().as_ptr();
                    let id = unsafe { ndk_sys::AInputEvent_getDeviceId(raw) };
                    let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(raw) };
                    let action = unsafe { ndk_sys::AKeyEvent_getAction(raw) };
                    let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(raw) };
                    if crate::dc_stylus_native_capture(id, code, action, repeat) {
                        queue.finish_event(ndk_event, true);
                        return true;
                    }
                }
""", "NativeActivity input interception")
    assert native.read_text().count("queue.pre_dispatch(ndk_event)") == 1
    assert "dc_stylus_native_take" in lib.read_text()
    print("PASS: whitelisted Magic-Pencil native events captured before Android winit/IME")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: stage_v0201_native.py DISPOSABLE_BUILDER")
    main(Path(sys.argv[1]))
