#!/usr/bin/env python3
"""EffectCraft-only verified Magic-Pencil native AInputQueue capture (TEST ONLY).

Keep the published vendor immutable. Java supplies the device IDs after checking
InputDevice.getName(). Non-pen keyboards, IME, touch and trackpad are untouched.
"""
from pathlib import Path
import sys

STATE = r'''
// EffectCraft TEST-only Magic-Pencil 4s native queue. The Java Activity is
// the sole authority for the device-ID allowlist, not guessed source masks.
#[cfg(feature = "native-activity")]
struct EcWheelKeys {
    enabled: bool,
    allowed: Vec<i32>,
    pending: Vec<i32>,
    last_single: Option<std::time::Instant>,
    last_double: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static EC_WHEEL_KEYS: std::sync::Mutex<EcWheelKeys> =
    std::sync::Mutex::new(EcWheelKeys {
        enabled: false,
        allowed: Vec::new(),
        pending: Vec::new(),
        last_single: None,
        last_double: None,
    });

#[cfg(feature = "native-activity")]
pub fn ec_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut state) = EC_WHEEL_KEYS.lock() {
        let ids: Vec<i32> = ids.iter().copied().filter(|id| *id > 0).take(16).collect();
        if state.enabled != enabled || state.allowed != ids {
            state.pending.clear();
            state.last_single = None;
            state.last_double = None;
        }
        state.enabled = enabled;
        state.allowed = ids;
    }
}

#[cfg(feature = "native-activity")]
pub fn ec_stylus_native_capture(device: i32, key: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = EC_WHEEL_KEYS.lock() else { return false };
    if !state.enabled || !state.allowed.contains(&device) || (key != 19 && key != 20) {
        return false;
    }
    // Consume both DOWN and UP; queue only the first release.
    if action == 1 && repeat == 0 {
        let now = std::time::Instant::now();
        let last = if key == 19 { state.last_double } else { state.last_single };
        if last.is_none_or(|t| now.duration_since(t) >= std::time::Duration::from_millis(650))
            && state.pending.len() < 16 {
            state.pending.push(if key == 19 { 2 } else { 1 });
            if key == 19 { state.last_double = Some(now); }
            else { state.last_single = Some(now); }
        }
    }
    true
}

#[cfg(feature = "native-activity")]
pub fn ec_stylus_native_take() -> Vec<i32> {
    if let Ok(mut state) = EC_WHEEL_KEYS.lock() {
        std::mem::take(&mut state.pending)
    } else { Vec::new() }
}
'''

INJECT = r'''            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {
                // Verified HONOR Magic-Pencil keys only. Intercept BEFORE
                // winit converts stylus DPAD to generic keyboard arrows.
                if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                    let raw = key.ptr().as_ptr();
                    let id = unsafe { ndk_sys::AInputEvent_getDeviceId(raw) };
                    let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(raw) };
                    let action = unsafe { ndk_sys::AKeyEvent_getAction(raw) };
                    let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(raw) };
                    if crate::ec_stylus_native_capture(id, code, action, repeat) {
                        queue.finish_event(ndk_event, true);
                        return true;
                    }
                }
'''

def patch(root: Path):
    lib = root / "src/lib.rs"
    activity = root / "src/native_activity/mod.rs"
    old = "            if let Some(ndk_event) = queue.pre_dispatch(ndk_event) {"
    a, b = lib.read_text(), activity.read_text()
    if "ec_stylus_configure" in a or b.count(old) != 1:
        raise RuntimeError("STOP: Android native stylus queue already changed")
    if b.count("queue.pre_dispatch(ndk_event)") != 1:
        raise RuntimeError("STOP: native input queue ownership changed")
    lib.write_text(a + "\n" + STATE)
    activity.write_text(b.replace(old, INJECT, 1))
    print("PASS: native-activity captures only named Magic-Pencil 4s IDs, not physical keyboard arrows")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("usage: patch_stylus_native.py <vendor/android-activity>")
    patch(Path(sys.argv[1]))
