#!/usr/bin/env python3
"""PhotoCraft Android.2: guarded touchpad canvas pan/pinch routing.

Executed only in the disposable GitHub Actions runner after the previously
device-tested PhotoCraft Android.1 overlays. No production source, signing,
release tags or user data are modified.
"""
import argparse
from pathlib import Path
import subprocess

UPSTREAM = "7c12f647150f8e7b2e07718f7993b1fcaa57fefe"

def patch(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    n = content.count(old)
    if n != 1:
        raise RuntimeError(f"PhotoCraft trackpad overlay anchor changed: {path} {n}: {old[:90]!r}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")

def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("upstream", "adapter", "vendor"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    sha = subprocess.check_output(
        ["git", "-C", str(a.upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if sha != UPSTREAM:
        raise RuntimeError(f"Refusing unreviewed upstream {sha}")

    host = a.adapter / "src/lib.rs"
    wheel = a.adapter / "src/trackpad_wheel.rs"
    canvas = a.adapter / "src/canvas_gesture.rs"
    activity = a.adapter / "java/com/artcraft/photocraft/PhotoCraftActivity.java"
    android_lib = a.vendor / "android-activity/src/lib.rs"
    native = a.vendor / "android-activity/src/native_activity/mod.rs"

    patch(a.adapter / "Cargo.toml",
          'version = "0.20.2-android.1"', 'version = "0.20.2-android.2"')

    # Keep the existing menu-specific path, stylus, mouse and touch handling.
    # Route trackpad canvas gestures only when within the canvas viewport.
    with canvas.open("a", encoding="utf-8") as f:
        f.write("""
impl CanvasTouchGestures {
    /// Android touchpad position and deltas are egui points, not device pixels.
    /// This queues only a VIEW transform; no editor, image or document mutation.
    pub(crate) fn trackpad_view(
        &mut self, rect: egui::Rect, at: egui::Pos2, delta: egui::Vec2, scale: f32,
    ) -> bool {
        if !Self::canvas_region(rect).contains(at)
            || !at.x.is_finite() || !at.y.is_finite()
            || !delta.x.is_finite() || !delta.y.is_finite()
            || !scale.is_finite() || !(0.2..=5.0).contains(&scale)
        { return false; }
        if delta.length_sq() < 0.0001 && (scale - 1.0).abs() < 0.0001 { return false; }
        if self.moves.len() >= 128 { return false; }
        self.moves.push(ViewMove {
            from: at, to: at + delta,
            scale: scale.clamp(0.75, 1.25), degrees: 0.0,
        });
        true
    }
}
""")

    patch(host,
          "trackpad_wheel::route(&self.bridge, ctx, raw);",
          "trackpad_wheel::route(&self.bridge, ctx, raw, &mut self.canvas_gesture);")

    # The Java bridge supplies scale events even when MagicOS sends them to
    # Activity instead of the NativeActivity/winit input queue.
    patch(activity,
          '    public String pcTrackpadScrollPoll() { return artcraftTrackpadScroll.poll(); }',
          """    public String pcTrackpadScrollPoll() { return artcraftTrackpadScroll.poll(); }
    private final ConcurrentLinkedQueue<String> artcraftTrackpadPinch = new ConcurrentLinkedQueue<>();
    public String pcTrackpadPinchPoll() { return artcraftTrackpadPinch.poll(); }
""")
    patch(activity,
          "        return super.dispatchGenericMotionEvent(event);",
          """        // API 34+ trackpad pinch is a RELATIVE scale, normally on ACTION_MOVE.
        // Collect history: discarding batched samples makes zoom jerky or inert.
        int source = event.getSource();
        boolean pad = (source & android.view.InputDevice.SOURCE_TOUCHPAD)
            == android.view.InputDevice.SOURCE_TOUCHPAD;
        boolean mouse = (source & android.view.InputDevice.SOURCE_MOUSE)
            == android.view.InputDevice.SOURCE_MOUSE;
        if (android.os.Build.VERSION.SDK_INT >= 34 && (pad || mouse)
            && (event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE
                || event.getActionMasked() == android.view.MotionEvent.ACTION_SCROLL
                || event.getActionMasked() == android.view.MotionEvent.ACTION_HOVER_MOVE)) {
            int count = event.getHistorySize();
            android.view.View decor = getWindow().getDecorView();
            for (int i = 0; i <= count; i++) {
                float scale = i == count
                    ? event.getAxisValue(android.view.MotionEvent.AXIS_GESTURE_PINCH_SCALE_FACTOR)
                    : event.getHistoricalAxisValue(
                        android.view.MotionEvent.AXIS_GESTURE_PINCH_SCALE_FACTOR, 0, i);
                if (Float.isFinite(scale) && scale > 0.0f
                    && Math.abs(scale - 1.0f) > 0.0001f
                    && artcraftTrackpadPinch.size() < 64) {
                    artcraftTrackpadPinch.offer(scale + "," + event.getX() + ","
                        + event.getY() + "," + decor.getWidth() + ","
                        + decor.getHeight());
                }
            }
        }
        return super.dispatchGenericMotionEvent(event);""")

    # Some physical pads expose two pointers rather than the API 34 gesture
    # axis. Their coordinates are not screen touches; do not modify touchscreen
    # or stylus paths and do not consume the original Java event.
    patch(activity, "    private float artcraftTrackpadY;",
          "    private float artcraftTrackpadY;\n    private float artcraftTrackpadSeparation;")
    patch(activity,
          """            artcraftTrackpadY = cy;
            artcraftTrackpadMoving = true;""",
          """            // Two touchpad contacts are a fallback when no pinch axis exists.
            float ddx = event.getX(1) - event.getX(0);
            float ddy = event.getY(1) - event.getY(0);
            float distance = (float)Math.hypot(ddx, ddy);
            if (event.getActionMasked() == android.view.MotionEvent.ACTION_MOVE
                && artcraftTrackpadSeparation > 8.0f && distance > 8.0f
                && artcraftTrackpadPinch.size() < 64) {
                float scale = distance / artcraftTrackpadSeparation;
                if (Float.isFinite(scale) && Math.abs(scale - 1.0f) > .002f) {
                    android.view.View decor = getWindow().getDecorView();
                    artcraftTrackpadPinch.offer(scale + "," + cx + "," + cy
                        + "," + decor.getWidth() + "," + decor.getHeight());
                }
            }
            artcraftTrackpadSeparation = distance;
            artcraftTrackpadY = cy;
            artcraftTrackpadMoving = true;""")
    patch(activity,
          "            artcraftTrackpadMoving = false;",
          "            artcraftTrackpadMoving = false;\n            artcraftTrackpadSeparation = 0.0f;")

    patch(host,
          '    fn poll_hardware_key(&self) -> Result<Option<String>, String> {',
          """    fn poll_trackpad_pinch(&self) -> Result<Option<String>, String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<Option<String>> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let result = env.call_method(
                &*activity, jni_str!("pcTrackpadPinchPoll"),
                jni_sig!("()Ljava/lang/String;"), &[],
            )?.l()?;
            if result.is_null() { return Ok(None); }
            let value = JString::cast_local(env, result)?;
            Ok(Some(value.try_to_string(env)?))
        }).map_err(|e| e.to_string())
    }

    fn poll_hardware_key(&self) -> Result<Option<String>, String> {""")

    # NativeActivity may receive pointer gesture axes instead of Java's
    # dispatchGenericMotionEvent. Keep a bounded, read-once native sample queue.
    with android_lib.open("a", encoding="utf-8") as f:
        f.write("""
#[cfg(feature = "native-activity")]
static PC_PAD_GESTURES: std::sync::Mutex<Vec<[f32; 5]>> =
    std::sync::Mutex::new(Vec::new());

#[cfg(feature = "native-activity")]
pub fn pc_pad_gesture_push(sample: [f32; 5]) {
    if let Ok(mut state) = PC_PAD_GESTURES.lock() {
        if state.len() < 128 { state.push(sample); }
    }
}

#[cfg(feature = "native-activity")]
pub fn pc_pad_gesture_take() -> Vec<[f32; 5]> {
    if let Ok(mut state) = PC_PAD_GESTURES.lock() {
        std::mem::take(&mut *state)
    } else {
        Vec::new()
    }
}
""")
    patch(native,
          "            let owner = crate::PHOTOCRAFT_INPUT_OWNER.load",
          """            // NativeActivity fallback for Android API 34+ trackpad gesture
            // axes; only SOURCE_TOUCHPAD/MOUSE, never touch-screen/pen input.
            if let ndk::event::InputEvent::MotionEvent(m) = &ndk_event {
                let ptr = m.ptr().as_ptr();
                let src = unsafe { ndk_sys::AInputEvent_getSource(ptr) };
                let pad = src & 0x100008 == 0x100008;
                let mouse = src & 0x2002 == 0x2002;
                if pad || mouse {
                    let action = unsafe { ndk_sys::AMotionEvent_getAction(ptr) } & 255;
                    let count = unsafe { ndk_sys::AMotionEvent_getPointerCount(ptr) };
                    if count > 0 && matches!(action, 2 | 7 | 8) {
                        let history = unsafe { ndk_sys::AMotionEvent_getHistorySize(ptr) };
                        for i in 0..=history {
                            let axis = |code| unsafe {
                                if i < history {
                                    ndk_sys::AMotionEvent_getHistoricalAxisValue(ptr, code, 0, i)
                                } else {
                                    ndk_sys::AMotionEvent_getAxisValue(ptr, code, 0)
                                }
                            };
                            let dx = axis(50); // AXIS_GESTURE_SCROLL_X_DISTANCE
                            let dy = -axis(51); // AXIS_GESTURE_SCROLL_Y_DISTANCE
                            let raw_scale = axis(52); // AXIS_GESTURE_PINCH_SCALE_FACTOR
                            let scale = if raw_scale > 0.0 { raw_scale } else { 1.0 };
                            if dx.is_finite() && dy.is_finite() && scale.is_finite()
                                && (dx.abs() + dy.abs() > 0.01 || (scale-1.0).abs() > 0.0001)
                            {
                                crate::pc_pad_gesture_push([
                                    dx, dy, scale,
                                    unsafe { ndk_sys::AMotionEvent_getX(ptr, 0) },
                                    unsafe { ndk_sys::AMotionEvent_getY(ptr, 0) },
                                ]);
                            }
                        }
                    }
                }
            }
            let owner = crate::PHOTOCRAFT_INPUT_OWNER.load""")

    patch(wheel,
          "use crate::AndroidFileBridge;",
          "use crate::{AndroidFileBridge, canvas_gesture::CanvasTouchGestures};")
    patch(wheel,
          "pub(crate) fn route(bridge: &AndroidFileBridge, ctx: &egui::Context, raw: &mut RawInput) {",
          """pub(crate) fn route(
    bridge: &AndroidFileBridge, ctx: &egui::Context, raw: &mut RawInput,
    gestures: &mut CanvasTouchGestures,
) {""")

    patch(wheel,
          "    let rect = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());",
          """    let rect = raw.screen_rect.unwrap_or_else(|| ctx.content_rect());
    let ppp = ctx.pixels_per_point().max(0.1);
    let native = android_activity::pc_pad_gesture_take();
    let native_scroll = native.iter().any(|g| g[0].abs() + g[1].abs() > 0.01);
    let native_pinch = native.iter().any(|g| (g[2] - 1.0).abs() > 0.0001);
    let mut native_canvas = false;
    if menu.is_none() {
        for [dx, dy, scale, x, y] in native {
            let at = Pos2::new(rect.left() + x / ppp, rect.top() + y / ppp);
            let fallback = ctx.pointer_hover_pos().unwrap_or(rect.center());
            let pos = if rect.contains(at) { at } else { fallback };
            native_canvas |= gestures.trackpad_view(rect, pos, Vec2::new(dx / ppp, dy / ppp), scale);
        }
    }""")

    patch(wheel,
          "        if native_wheel_present || native_delta != 0.0 { continue; }",
          "        if native_wheel_present || native_delta != 0.0 || native_scroll { continue; }")

    patch(wheel,
          "    if let Some((key, offset, max)) = menu {",
          """    // Android Java bridge fallback when the native queue did not observe
    // the relative touchpad pinch. Native takes precedence to avoid duplicates.
    for _ in 0..64 {
        let Ok(Some(data)) = bridge.poll_trackpad_pinch() else { break; };
        if native_pinch || menu.is_some() { continue; }
        let values: Vec<f32> = data.split(',').filter_map(|s| s.parse().ok()).collect();
        let [scale, x, y, width, height]: [f32; 5] = match values.try_into() {
            Ok(v) => v, Err(_) => continue,
        };
        if width < 1.0 || height < 1.0 { continue; }
        let pos = Pos2::new(
            rect.left() + x.clamp(0.0, width) / width * rect.width(),
            rect.top() + y.clamp(0.0, height) / height * rect.height(),
        );
        let _ = gestures.trackpad_view(rect, pos, Vec2::ZERO, scale);
    }
    if let Some((key, offset, max)) = menu {""")

    data = wheel.read_text(encoding="utf-8")
    if not data.endswith("\n}\n"):
        raise RuntimeError("Trackpad route no longer ends with known closing brace")
    data = data[:-2] + """
    // Consume ONLY trackpad canvas-wheel events. Menus/panels retain their
    // existing scroll routing, and ordinary mouse wheels stay unchanged.
    let pointer = raw.events.iter().rev().find_map(|event| match event {
        Event::PointerMoved(pos) => Some(*pos), _ => None,
    }).or_else(|| ctx.pointer_hover_pos()).unwrap_or(rect.center());
    raw.events.retain(|event| {
        if let Event::MouseWheel { source, delta, unit, modifiers, .. } = event {
            if menu.is_none() && !modifiers.any()
                && (*source == MouseWheelSource::Trackpad || native_scroll)
            {
                let multiplier = match unit {
                    MouseWheelUnit::Point => 1.0,
                    MouseWheelUnit::Line => 42.0,
                    MouseWheelUnit::Page => rect.height(),
                };
                if native_scroll && native_canvas {
                    // Native gesture axes already supplied this canvas movement.
                    return false;
                } else if !native_scroll && gestures.trackpad_view(rect, pointer, *delta * multiplier, 1.0) {
                    return false;
                }
            }
        }
        true
    });
}
"""
    wheel.write_text(data, encoding="utf-8")

    assert 'pcTrackpadPinchPoll' in activity.read_text()
    assert 'pc_pad_gesture_take' in wheel.read_text()
    assert 'trackpad_view' in canvas.read_text()
    print("PASS: guarded Android touchpad pinch + two-finger canvas pan routing staged.")
    print("NOTE: remains unverified on HONOR MagicPad 4 until device testing.")

if __name__ == "__main__":
    main()
