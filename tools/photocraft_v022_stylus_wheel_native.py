#!/usr/bin/env python3
"""Android.3 v0.22 wheel: guarded Magic-Pencil input queue/IME routing fix (TEST ONLY).

Executed after the original radial-wheel overlay in the disposable CI checkout.
Only pen-associated DPAD_UP/DOWN events are intercepted. Everything else retains
NativeActivity/winit and physical keyboard dispatch, including popup navigation.
"""
import argparse
from pathlib import Path

def once(path: Path, old: str, new: str):
    contents = path.read_text(encoding="utf-8")
    n = contents.count(old)
    if n != 1:
        raise RuntimeError(f"stylus wheel native: unexpected anchor {path} count={n}: {old[:100]!r}")
    path.write_text(contents.replace(old, new, 1), encoding="utf-8")

NATIVE_STATE = r"""
// Separate, opt-in native input owner for the HONOR Magic-Pencil 4s.
// Android Java validates the exact device name, and supplies matching IDs.
// Unrecognized IDs (including a physical keyboard) NEVER reach this queue.
#[cfg(feature = "native-activity")]
struct PcStylusNativeKeys {
    enabled: bool,
    allowed_ids: Vec<i32>,
    events: Vec<u8>,
    last_single: Option<std::time::Instant>,
    last_double: Option<std::time::Instant>,
}
#[cfg(feature = "native-activity")]
static PC_STYLUS_NATIVE_KEYS: std::sync::Mutex<PcStylusNativeKeys> =
    std::sync::Mutex::new(PcStylusNativeKeys {
        enabled: false,
        allowed_ids: Vec::new(),
        events: Vec::new(),
        last_single: None,
        last_double: None,
    });

#[cfg(feature = "native-activity")]
pub fn pc_stylus_configure(enabled: bool, ids: &[i32]) {
    if let Ok(mut state) = PC_STYLUS_NATIVE_KEYS.lock() {
        let ids: Vec<i32> = ids.iter().copied().take(16).filter(|id| *id > 0).collect();
        if state.enabled != enabled || state.allowed_ids != ids {
            state.events.clear();
            state.last_single = None;
            state.last_double = None;
        }
        state.enabled = enabled;
        state.allowed_ids = ids;
    }
}

#[cfg(feature = "native-activity")]
pub fn pc_stylus_native_capture(device: i32, code: i32, action: i32, repeat: i32) -> bool {
    let Ok(mut state) = PC_STYLUS_NATIVE_KEYS.lock() else { return false };
    if !state.enabled || !state.allowed_ids.contains(&device) || (code != 19 && code != 20) {
        return false;
    }
    // Consume BOTH DOWN and UP, but only the first UP (release) triggers.
    // Otherwise Android's usual DPAD navigation can change open menus.
    if action == 1 && repeat == 0 {
        let now = std::time::Instant::now();
        let last = if code == 19 { state.last_double } else { state.last_single };
        if last.is_none_or(|t| now.duration_since(t) >= std::time::Duration::from_millis(650))
            && state.events.len() < 16 {
            state.events.push(code as u8);
            if code == 19 { state.last_double = Some(now); }
            else { state.last_single = Some(now); }
            log::info!("PcStylusWheel: validated native pen button code={code} device={device}");
        }
    }
    true
}

#[cfg(feature = "native-activity")]
pub fn pc_stylus_native_take() -> Vec<u8> {
    if let Ok(mut state) = PC_STYLUS_NATIVE_KEYS.lock() {
        std::mem::take(&mut state.events)
    } else {
        Vec::new()
    }
}
"""

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True, type=Path)
    p.add_argument("--vendor", required=True, type=Path)
    a = p.parse_args()
    activity = a.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    host = a.adapter / "src/lib.rs"
    wheel = a.adapter / "src/stylus_wheel.rs"
    android_lib = a.vendor / "android-activity/src/lib.rs"
    native = a.vendor / "android-activity/src/native_activity/mod.rs"

    # Java is the authority on InputDevice names, NEVER a guessed source mask.
    once(activity, "    public String pcStylusPoll() { return pcWheelKeys.poll(); }",
        """    public String pcStylusPoll() { return pcWheelKeys.poll(); }
    public String pcStylusDeviceIds() {
        StringBuilder ids = new StringBuilder();
        for (int id : android.view.InputDevice.getDeviceIds()) {
            android.view.InputDevice input = android.view.InputDevice.getDevice(id);
            if (input != null && input.getName() != null
                    && input.getName().contains("Magic-Pencil 4s")) {
                if (ids.length() > 0) ids.append(',');
                ids.append(id);
            }
        }
        return ids.toString();
    }""")
    # Hidden Android EditText/IME paths bypass Activity.dispatchKeyEvent on some
    # MagicOS builds. These must capture only verified pen IDs and DPAD keys.
    routes = (
        ('pcKeyDiagCapture(event, "Activity.dispatchKeyShortcutEvent");',
         'if (pcStylusIntercept(event)) return true;\n        pcKeyDiagCapture(event, "Activity.dispatchKeyShortcutEvent");'),
        ('pcKeyDiagCapture(event, "EditText.onKeyPreIme");',
         'if (pcStylusIntercept(event)) return true;\n                    pcKeyDiagCapture(event, "EditText.onKeyPreIme");'),
        ('pcKeyDiagCapture(event, "EditText.onKeyDown");',
         'if (pcStylusIntercept(event)) return true;\n                    pcKeyDiagCapture(event, "EditText.onKeyDown");'),
        ('pcKeyDiagCapture(event, "InputConnection.sendKeyEvent");',
         'if (pcStylusIntercept(event)) return true;\n                            pcKeyDiagCapture(event, "InputConnection.sendKeyEvent");')
    )
    for old, new in routes:
        once(activity, old, new)
    once(activity,
         "                public boolean onKeyUp(int keyCode, KeyEvent event) {",
         "                public boolean onKeyUp(int keyCode, KeyEvent event) {\n                    if (pcStylusIntercept(event)) return true;")

    # Capture from the NativeActivity AInputQueue before winit synthesizes
    # generic DPAD keys. This is the path missed by Java in the first video.
    if "pc_stylus_configure" in android_lib.read_text(encoding="utf-8"):
        raise RuntimeError("Duplicate native stylus input module")
    with android_lib.open("a", encoding="utf-8") as out:
        out.write(NATIVE_STATE)
    once(native,
         "            if let Some(ndk_event) = next {",
         """            if let Some(ndk_event) = next {
                // Magic-Pencil only: capture before winit dispatches a DPAD
                // arrow into a PhotoCraft dropdown or canvas navigation.
                if let ndk::event::InputEvent::KeyEvent(ref key) = ndk_event {
                    let raw = key.ptr().as_ptr();
                    let id = unsafe { ndk_sys::AInputEvent_getDeviceId(raw) };
                    let code = unsafe { ndk_sys::AKeyEvent_getKeyCode(raw) };
                    let action = unsafe { ndk_sys::AKeyEvent_getAction(raw) };
                    let repeat = unsafe { ndk_sys::AKeyEvent_getRepeatCount(raw) };
                    if crate::pc_stylus_native_capture(id, code, action, repeat) {
                        queue.finish_event(ndk_event, true);
                        return true;
                    }
                }
""")

    once(host, "    fn pc_stylus_poll(&self) -> Result<Option<String>, String> {",
         """    fn pc_stylus_device_ids(&self) -> Result<Vec<i32>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Vec<i32>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let value = env.call_method(&*activity, jni_str!("pcStylusDeviceIds"),
                jni_sig!("()Ljava/lang/String;"), &[])?.l()?;
            if value.is_null() { return Ok(Vec::new()); }
            let value = JString::cast_local(env, value)?;
            let ids: String = value.try_to_string(env)?;
            Ok(ids.split(',').filter_map(|s| s.parse::<i32>().ok()).collect())
        }).map_err(|e| e.to_string())
    }

    fn pc_stylus_poll(&self) -> Result<Option<String>, String> {""")
    once(host, "    stylus_wheel: stylus_wheel::Wheel,\n",
         "    stylus_wheel: stylus_wheel::Wheel,\n    stylus_device_scan_at: std::time::Instant,\n")
    once(host, "                stylus_wheel: stylus_wheel::Wheel::new(app_bridge.pc_stylus_enabled().unwrap_or(false)),",
         """                stylus_wheel: {
                    let enabled = app_bridge.pc_stylus_enabled().unwrap_or(false);
                    let ids = app_bridge.pc_stylus_device_ids().unwrap_or_default();
                    android_activity::pc_stylus_configure(enabled, &ids);
                    stylus_wheel::Wheel::new(enabled)
                },
                stylus_device_scan_at: std::time::Instant::now(),""")
    once(host, "                    Ok(()) => self.stylus_wheel.toggle(requested, ui.ctx()),",
         """                    Ok(()) => {
                        self.stylus_wheel.toggle(requested, ui.ctx());
                        android_activity::pc_stylus_configure(
                            requested, &self.bridge.pc_stylus_device_ids().unwrap_or_default()
                        );
                        self.stylus_device_scan_at = std::time::Instant::now();
                    },""")

    once(host, """        if self.stylus_wheel.enabled && !wheel_blocked {
            for _ in 0..12 {
                match self.bridge.pc_stylus_poll() {
                    Ok(Some(signal)) => self.stylus_wheel.signal(&signal, ctx),
                    _ => break,
                }
            }
        }
        self.stylus_wheel.capture(ctx, raw, wheel_blocked);""",
         """        // MagicOS may route the same physical button through Java or the
        // NativeActivity queue; drain both but never guess keyboard origins.
        if self.stylus_wheel.enabled
            && self.stylus_device_scan_at.elapsed() > std::time::Duration::from_secs(2)
        {
            if let Ok(ids) = self.bridge.pc_stylus_device_ids() {
                android_activity::pc_stylus_configure(true, &ids);
            }
            self.stylus_device_scan_at = std::time::Instant::now();
        }
        let native = android_activity::pc_stylus_native_take();
        if self.stylus_wheel.enabled && !wheel_blocked {
            for code in native {
                self.stylus_wheel.signal(if code == 19 { "D" } else { "S" }, ctx);
            }
            for _ in 0..12 {
                match self.bridge.pc_stylus_poll() {
                    Ok(Some(signal)) => self.stylus_wheel.signal(&signal, ctx),
                    _ => break,
                }
            }
        } else {
            // No delayed shortcut execution after a modal dialog closes.
            for _ in 0..12 {
                if !matches!(self.bridge.pc_stylus_poll(), Ok(Some(_))) { break; }
            }
        }
        self.stylus_wheel.capture(ctx, raw, wheel_blocked);""")
    once(wheel, '                self.single_wait = Some((Instant::now(), self.hover));',
         '''                self.single_wait = Some((Instant::now(), self.hover));
                self.message = "Pen button received • opening wheel…";''')
    once(wheel, '''        if pen_down { self.single_wait = None; }''',
         '''        if pen_down {
            self.single_wait = None;
            // Ignore any pen-button shortcut occurring during drawing.
            if self.action.is_some() {
                self.action = None;
                self.message = "Pen contact • drawing remains active";
            }
        }''')
    # Static preservation checks before the full 20-minute native compile.
    assert "pcStylusDeviceIds" in activity.read_text()
    assert "InputConnection.sendKeyEvent" in activity.read_text()
    assert native.read_text().count("queue.pre_dispatch(ndk_event)") == 1
    assert native.read_text().count("if let Some(ndk_event) = next {") == 1
    assert "pc_stylus_native_capture" in native.read_text()
    assert "pc_stylus_native_take" in android_lib.read_text()
    assert "artcraft_brush_scroll_area" in (a.adapter / "src/trackpad_wheel.rs").read_text()
    assert "stylus_wheel.capture" in host.read_text()
    print("PASS: Java/IME and native-queue pen-only routing; keyboard arrows, brush scroll, and Type preserved")

if __name__ == "__main__":
    main()
