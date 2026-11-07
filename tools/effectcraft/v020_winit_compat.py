#!/usr/bin/env python3
"""Rebase only EffectCraft's Android pointer-event adapter onto its pinned v0.20 winit.

This is run in an ISOLATED CI CHECKOUT, never against the published EffectCraft
APK, the shared production vendor folder or a production keystore. All changes
are limited to the pinned winit fork's Android backend. Preserve the fork's
newer IME reset APIs, keyboard path, window lifetime and other platform code.
"""
from pathlib import Path
import sys

WINIT_REV = "a517b3846ee8457d84ee4975110bfda6797c44dc"
ANDROID_REL = Path("src/platform_impl/android/mod.rs")
START = "            InputEvent::MotionEvent(motion_event) => {"
END = "            InputEvent::KeyEvent(key) => {"
OLD_IMPORT = "use android_activity::input::{\n    Axis, Button, InputEvent, KeyAction, Keycode, MotionAction, Source, ToolType,\n};"
PINNED_IMPORT = "use android_activity::input::{InputEvent, KeyAction, Keycode, MotionAction};"
HELPER_START = "/// Above this a scroll axis value"
HELPER_END = "struct PeekableReceiver<T> {"


def _exactly_one(text: str, needle: str, description: str) -> int:
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"STOP: {description} expected once; found {count}, review winit source drift"
        )
    return text.index(needle)


def apply(local: Path, pinned: Path) -> None:
    """Preserve official v0.20 APIs; transplant ONLY legacy Android mouse support."""
    original = local.read_text(encoding="utf-8")
    upstream = pinned.read_text(encoding="utf-8")

    _exactly_one(original, OLD_IMPORT, "existing Android mouse imports")
    _exactly_one(upstream, PINNED_IMPORT, "official v0.20 input imports")
    _exactly_one(original, HELPER_START, "mouse helper start")
    _exactly_one(original, HELPER_END, "mouse helper end")
    _exactly_one(upstream, HELPER_END, "upstream helper insertion anchor")
    if HELPER_START in upstream or "fn pointer_position(" in upstream:
        raise RuntimeError("STOP: upstream already has pointer helpers; cannot stack patches")
    if "reset_ime_with_request" not in upstream:
        raise RuntimeError("STOP: wrong upstream fork: IME reset support is missing")

    old_start = _exactly_one(original, START, "existing motion branch")
    old_end = _exactly_one(original, END, "existing keyboard branch")
    new_start = _exactly_one(upstream, START, "upstream motion branch")
    new_end = _exactly_one(upstream, END, "upstream keyboard branch")
    if old_start >= old_end or new_start >= new_end:
        raise RuntimeError("STOP: malformed Android input match; refuse to patch")

    old_motion = original[old_start:old_end]
    scroll_anchor = "MotionAction::Scroll if pointer_class => {"
    if old_motion.count(scroll_anchor) != 1:
        raise RuntimeError("STOP: expected one Android mouse scroll source guard in legacy winit")
    # Some Android tablet trackpads identify a two-finger AXIS_VSCROLL
    # gesture as a generic motion source, not Source::Touchpad/Mouse. This
    # must still be a MouseWheel event; the existing code forwards it only
    # when a pointer is classified as a mouse. The rest of pointer and
    # touch/stylus gesture handling remains unchanged.
    old_motion = old_motion.replace(scroll_anchor, "MotionAction::Scroll => {", 1)
    upstream_motion = upstream[new_start:new_end]
    if "pointer_class" not in old_motion or "MouseWheel" not in old_motion or "MouseInput" not in old_motion:
        raise RuntimeError("STOP: local mouse/scroll/right-click features missing")
    if "None // TODO mouse events" not in upstream_motion:
        raise RuntimeError("STOP: upstream Android motion handling changed; review manually")
    helper_start = original.index(HELPER_START)
    helper_end = original.index(HELPER_END, helper_start)
    extra = original[helper_start:helper_end]
    if "MAX_LINE_SCROLL" not in extra or "fn android_mouse_button(" not in extra:
        raise RuntimeError("STOP: existing pointer helpers are incomplete")

    # Replace the *motion* block only; preserve the pinned upstream keyboard
    # branch and its separate IME-reset dispatch implementation intact.
    merged = upstream[:new_start] + old_motion + upstream[new_end:]
    merged = merged.replace(PINNED_IMPORT, OLD_IMPORT, 1)
    merged = merged.replace(HELPER_END, extra + HELPER_END, 1)
    if merged.count("reset_ime_with_request") != upstream.count("reset_ime_with_request"):
        raise RuntimeError("STOP: incompatible IME reset change detected")
    if merged.count(END) != 1 or merged.count("MouseWheel") < 1 or "MotionAction::Scroll if pointer_class => {" in merged or "MotionAction::Scroll => {" not in merged:
        raise RuntimeError("STOP: generated Android input patch failed structural checks")
    pinned.write_text(merged, encoding="utf-8")
    print("PASS: pinned winit IME and Android mouse/hover/wheel/secondary-click paths preserved")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: v020_winit_compat.py <legacy-vendor-winit>/mod.rs <pinned-winit>/mod.rs")
    apply(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
