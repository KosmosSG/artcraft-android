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
    x = require_once(target, block_start, "Pinned fork motion block")
    y = require_once(target, block_end, "Pinned fork motion block")
    if b <= a or y <= x:
        raise SystemExit("Motion block marker order is unexpected")
    motion = donor[a:b]
    for required in ("MotionAction::Scroll", "MotionAction::HoverMove", "MouseWheel", "MouseInput", "event::WindowEvent::Touch"):
        if required not in motion:
            raise SystemExit(f"ArtCraft motion block missing required behavior: {required}")
    target = target[:x] + motion + target[y:]
    if "pub fn reset_ime_with_request" in target:
        raise SystemExit("Unexpected IME window code inside Android motion module")

    target_path.write_text(target)
    print("Preserved Storytold winit IME/lifecycle; added ArtCraft mouse/hover/wheel/touch Android translation")

if __name__ == "__main__":
    main()
