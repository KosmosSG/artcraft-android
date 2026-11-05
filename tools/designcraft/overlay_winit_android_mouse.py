#!/usr/bin/env python3
"""Port only the ArtCraft Android mouse/touch translation onto pinned Storytold winit.

The DesignCraft 0.16 egui fork requires winit IME APIs absent from the suite's
older vendored winit. Start from the official, exact source-locked Storytold
fork; copy *only* the Android motion handler and associated helpers, keeping
all upstream IME, lifecycle, keyboard, and window implementation changes.

This helper intentionally refuses unknown source layouts rather than silently
producing a broken or feature-regressed Android build.
"""
from pathlib import Path
import sys

def require_once(text: str, token: str, label: str) -> int:
    if text.count(token) != 1:
        raise SystemExit(f"{label}: expected exactly one {token!r}, got {text.count(token)}")
    return text.index(token)

def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: overlay_winit_android_mouse.py <suite-vendored-android-mod> <pinned-fork-android-mod>")
    donor_path, target_path = map(Path, sys.argv[1:])
    donor, target = donor_path.read_text(), target_path.read_text()
    donor_import = """use android_activity::input::{
    Axis, Button, InputEvent, KeyAction, Keycode, MotionAction, Source, ToolType,
};"""
    fork_import = "use android_activity::input::{InputEvent, KeyAction, Keycode, MotionAction};"
    require_once(donor, donor_import, "ArtCraft mouse source")
    require_once(target, fork_import, "Storytold pinned fork")
    # Do not replace the entire winit Android module: its IME/window extensions
    # must stay exactly as shipped with official DesignCraft v0.16.0.
    target = target.replace(fork_import, donor_import, 1)
    # Trackpads expose Vscroll/Hscroll only when explicitly enabled by
    # GameActivity. Without these, two-finger scrolling silently reads zero.
    redraw = "        let redraw_flag = SharedFlag::new();"
    require_once(target, redraw, "Pinned Storytold event loop")
    target = target.replace(redraw, """        android_app.enable_motion_axis(Axis::Vscroll);
        android_app.enable_motion_axis(Axis::Hscroll);
""" + redraw, 1)


    helpers_start = "/// Above this a scroll axis value"
    helpers_end = "struct PeekableReceiver<T>"
    a = require_once(donor, helpers_start, "ArtCraft mouse helpers")
    b = require_once(donor, helpers_end, "ArtCraft mouse helpers")
    if b <= a:
        raise SystemExit("Invalid ordering for Android mouse helpers")
    helpers = donor[a:b]
    require_once(target, helpers_end, "Pinned fork helper insertion")
    if "fn android_mouse_button(" in target:
        raise SystemExit("Pinned fork already has an Android mouse mapping; review the fork before reapplying")
    target = target.replace(helpers_end, helpers + helpers_end, 1)

    block_start = "            InputEvent::MotionEvent(motion_event) => {"
    block_end = "            InputEvent::KeyEvent(key) => {"
    a = require_once(donor, block_start, "ArtCraft motion block")
    b = require_once(donor, block_end, "ArtCraft motion block")
    motion = donor[a:b]
    # Stylus hover is position-only. Contact continues through the touch arm.
    guard = "MotionAction::HoverExit\n                        if pointer_class =>"
    require_once(motion, guard, "hover classification")
    motion = motion.replace(guard, guard.replace("if pointer_class",
        "if pointer_class || matches!(tool_type, ToolType::Stylus | ToolType::Eraser)"))
    # Android may report both Down and ButtonPress for the same physical
    # click. action_button() is undefined on Down/Up. Track the primary edge
    # per device, preserving secondary buttons and click-only trackpad taps.
    for anchor, addition in [
        ("    redraw_flag: SharedFlag,", "    primary_devices: std::collections::HashSet<i32>,"),
        ("            redraw_flag,", "            primary_devices: Default::default(),"),
    ]:
        require_once(target, anchor, "per-device primary state")
        target = target.replace(anchor, anchor + "\n" + addition)
    start = motion.index("                                    // Android reports the primary")
    end = motion.index("                                        callback(", start)
    motion = motion[:start] + """                                    button_sent = true;
                                    let id = motion_event.device_id();
                                    let buttons = motion_event.button_state();
                                    let changed = match state {
                                        event::ElementState::Pressed => (buttons.primary() || buttons.0 == 0)
                                            && self.primary_devices.insert(id),
                                        event::ElementState::Released => self.primary_devices.remove(&id),
                                    };
                                    if changed {
""" + motion[end:]
    anchor = "                        trace!(\"Button {device_id:?}"
    require_once(motion, anchor, "button edge coalescing")
    motion = motion.replace(anchor, """                        if button == event::MouseButton::Left {
                            let changed = match state {
                                event::ElementState::Pressed => self.primary_devices.insert(motion_event.device_id()),
                                event::ElementState::Released => self.primary_devices.remove(&motion_event.device_id()),
                            };
                            if !changed { return InputStatus::Handled; }
                        }
""" + anchor)
    threshold = "if vertical.abs() <= MAX_LINE_SCROLL"
    require_once(motion, threshold, "scroll delta classification")
    motion = motion.replace(threshold, "if motion_event.source() != Source::Touchpad"
        " && vertical.fract() == 0.0 && horizontal.fract() == 0.0 && vertical.abs() <= MAX_LINE_SCROLL")
    action = "                match motion_event.action() {"
    motion = motion.replace(action, """                crate::platform::android::STYLUS_HOVER.store(
                    matches!(tool_type, ToolType::Stylus | ToolType::Eraser)
                        && matches!(motion_event.action(), MotionAction::HoverEnter | MotionAction::HoverMove),
                    std::sync::atomic::Ordering::Relaxed,
                );
""" + action, 1)
    platform = target_path.parents[2] / "platform/android.rs"
    platform.write_text(platform.read_text() + """
/// Whether the latest Android motion sample is an in-range pen hover.
pub static STYLUS_HOVER: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
""")
    for required in ("MotionAction::Scroll", "MotionAction::HoverMove", "MouseWheel", "MouseInput", "event::WindowEvent::Touch"):
        if required not in motion:
            raise SystemExit(f"ArtCraft motion block missing required behavior: {required}")
    # Field insertions above change byte offsets. Locate the original arm
    # only once all other edits to the target are complete.
    x = require_once(target, block_start, "Pinned fork motion block")
    y = require_once(target, block_end, "Pinned fork key block")
    if b <= a or y <= x:
        raise ValueError("Unexpected motion/key event order")
    target = target[:x] + motion + target[y:]
    # The pinned Storytold Android module deliberately implements this
    # no-op platform hook. egui-winit v0.37 calls it through winit::Window;
    # rejecting its presence incorrectly aborts every DesignCraft v0.16 build.
    if "pub fn reset_ime_with_request" not in target:
        raise SystemExit("Pinned Storytold Android IME reset hook was lost")

    target_path.write_text(target)
    print("Preserved Storytold winit IME/lifecycle; added ArtCraft mouse/hover/wheel/touch Android translation")

if __name__ == "__main__":
    main()
