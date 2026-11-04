#!/usr/bin/env python3
"""Reapply only reviewed Android pointer input support to FilmCraft v0.17 winit.

Upstream FilmCraft retains its exact pinned egui 0.37 / winit 0.30.13 API.
CI fetches the *same immutable winit commit* into a disposable local path,
replaces only Android pointer event code using the pinned builder's known
mouse-aware implementation, and changes only FilmCraft's temporary Cargo
workspace path patch. Finger/stylus touch handling is copied from the reviewed
builder, not redirected into the mouse route. Do not change any other app.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import re
import subprocess
import tomllib

PIN = "a517b3846ee8457d84ee4975110bfda6797c44dc"
GIT_URL = "https://github.com/storytold/winit.git"
IMPORT_OLD = "use android_activity::input::{InputEvent, KeyAction, Keycode, MotionAction};"
IMPORT_NEW = ("use android_activity::input::{\n"
              "    Axis, Button, InputEvent, KeyAction, Keycode, MotionAction, Source, ToolType,\n"
              "};")
HELP_START = "/// Above this a scroll axis value is a point-like"
HELP_END = "struct PeekableReceiver<T> {"
UP_HELP_ANCHOR = "struct PeekableReceiver<T> {"
MOTION_START = "            InputEvent::MotionEvent(motion_event) => {\n"
MOTION_END = "            InputEvent::KeyEvent(key) => {\n"
MANIFEST_PIN = ('winit = { git = "' + GIT_URL + '", rev = "' + PIN + '" }')
MANIFEST_PATH = 'winit = { path = "vendor/winit" }'

def once(s: str, old: str, new: str, why: str) -> str:
    if s.count(old) != 1:
        raise ValueError(f"STOP: {why} anchor changed ({s.count(old)} matches)")
    return s.replace(old, new, 1)

def splice_mouse_winit(upstream: str, reviewed: str) -> str:
    # Maintain the pinned upstream's other features, especially IME reset.
    for text in (MOTION_START, MOTION_END, UP_HELP_ANCHOR):
        if upstream.count(text) != 1 or reviewed.count(text) != 1:
            raise ValueError("STOP: upstream/reviewed mouse event source drift: " + text)
    if "None // TODO mouse events" not in upstream:
        raise ValueError("STOP: pinned upstream already changed Android mouse handling")
    if IMPORT_NEW not in reviewed:
        raise ValueError("STOP: builder mouse-aware imports were not found")
    helper_start = reviewed.index(HELP_START)
    helper_end = reviewed.index(HELP_END, helper_start)
    helpers = reviewed[helper_start:helper_end]
    block_start = reviewed.index(MOTION_START)
    block_end = reviewed.index(MOTION_END, block_start)
    mouse_block = reviewed[block_start:block_end]
    if not all(x in mouse_block for x in (
        "Source::Mouse", "Source::Touchpad", "ToolType::Mouse",
        "MotionAction::HoverMove", "MotionAction::Scroll",
        "WindowEvent::CursorMoved", "WindowEvent::MouseInput",
        "WindowEvent::MouseWheel", "WindowEvent::Touch",
    )):
        raise ValueError("STOP: reviewed builder lost a required pointer/touch path")
    original_start = upstream.index(MOTION_START)
    original_end = upstream.index(MOTION_END, original_start)
    staged = upstream[:original_start] + mouse_block + upstream[original_end:]
    staged = once(staged, IMPORT_OLD, IMPORT_NEW, "Android pointer imports")
    staged = once(staged, UP_HELP_ANCHOR, helpers + UP_HELP_ANCHOR, "mouse helper constants")
    assert staged.count("WindowEvent::CursorMoved") >= 1
    assert staged.count("WindowEvent::Touch") >= 1
    return staged

def path_override(manifest: str) -> str:
    patches = tomllib.loads(manifest)["patch"]["crates-io"]
    assert patches["winit"] == {"git": GIT_URL, "rev": PIN}, "STOP: wrong official winit pin"
    assert patches["egui-winit"] == {
        "git": "https://github.com/storytold/egui.git",
        "rev": "6d518fc799681571963842f95b55a6b68431b15a"
    }, "STOP: changed IME-compatible egui pin"
    return once(manifest, MANIFEST_PIN, MANIFEST_PATH, "pinned Cargo winit patch")

def stage(source: Path, reviewed: Path) -> None:
    source = source.resolve()
    reviewed = reviewed.resolve()
    if source.parts[-2:] != ("source", "filmcraft") or "filmcraft-builder" not in source.parts:
        raise ValueError("STOP: not disposable FilmCraft source tree")
    if reviewed.parts[-5:] != ("vendor", "winit", "src", "platform_impl", "android", "mod.rs")[-5:]:
        # Short suffix is checked separately to avoid using unknown builder paths.
        pass
    if reviewed.parts[-6:] != ("vendor", "winit", "src", "platform_impl", "android", "mod.rs"):
        raise ValueError("STOP: not approved builder mouse-aware winit file")
    if not reviewed.is_file():
        raise ValueError("STOP: missing reviewed builder pointer implementation")
    manifest = source / "Cargo.toml"
    if not manifest.is_file(): raise ValueError("STOP: missing FilmCraft upstream manifest")
    local = source / "vendor" / "winit"
    if local.exists(): raise ValueError("STOP: refusing to reuse unknown local winit checkout")
    # Fetch the exact upstream winit SHA. No production repo, tag or key is altered.
    local.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(local)], check=True)
    subprocess.run(["git", "-C", str(local), "fetch", "--quiet", "--depth", "1", GIT_URL, PIN], check=True)
    subprocess.run(["git", "-C", str(local), "checkout", "--quiet", "--detach", "FETCH_HEAD"], check=True)
    sha = subprocess.check_output(["git", "-C", str(local), "rev-parse", "HEAD"], text=True).strip()
    if sha != PIN: raise ValueError(f"STOP: unexpected official winit source {sha}")
    target = local / "src/platform_impl/android/mod.rs"
    if not target.is_file(): raise ValueError("STOP: winit Android backend missing")
    original = target.read_text()
    revised = splice_mouse_winit(original, reviewed.read_text())
    revised_manifest = path_override(manifest.read_text())
    target.write_text(revised)
    manifest.write_text(revised_manifest)
    print("PASS: FilmCraft official pinned winit + reviewed Android trackpad hover/scroll/buttons")
    print("PASS: mouse input maps to pointer events; fingers keep Touch; egui pin is unchanged")

def self_test() -> None:
    assert MANIFEST_PIN.endswith(PIN + '" }')
    up = (IMPORT_OLD + "\n" + HELP_END + "\n" + MOTION_START
          + "                let phase = match motion_event.action() {\n"
          + "                    _ => None // TODO mouse events\n"
          + "                };\n            },\n" + MOTION_END)
    builder = (IMPORT_NEW + "\n" + HELP_START + " constants\n"
               + "const MAX_LINE_SCROLL: f32 = 3.0;\n" + HELP_END
               + "\n" + MOTION_START
               + "let _ = Source::Mouse; let _ = Source::Touchpad; let _ = ToolType::Mouse;\n"
               + "let _ = MotionAction::HoverMove; let _ = MotionAction::Scroll;\n"
               + "let _ = WindowEvent::CursorMoved; let _ = WindowEvent::MouseInput;\n"
               + "let _ = WindowEvent::MouseWheel; let _ = WindowEvent::Touch;\n"
               + "            },\n" + MOTION_END)
    changed = splice_mouse_winit(up, builder)
    assert "TODO mouse events" not in changed
    assert "MAX_LINE_SCROLL" in changed
    for bad in (up.replace("TODO mouse events", "mouse handled"),
                up.replace(MOTION_START, MOTION_START * 2)):
        try: splice_mouse_winit(bad, builder)
        except ValueError: pass
        else: raise AssertionError("Must reject source drift")
    print("PASS: FilmCraft mouse/trackpad upstream fail-closed source-port tests")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("reviewed_builder_winit", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test: self_test()
    else:
        if args.source is None or args.reviewed_builder_winit is None:
            parser.error("source and reviewed_builder_winit required")
        stage(args.source, args.reviewed_builder_winit)
