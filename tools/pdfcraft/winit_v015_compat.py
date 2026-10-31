"""PDFCraft v0.15 candidate-only pinned winit/Android input compatibility.

The shared builder's old vendored winit lacks the IME API required by the
immutable egui-winit revision in PDFCraft v0.15. Start with the exact official
Storytold winit commit, then retain the existing Android mouse/scroll/hover
backend with only the upstream Android IME stubs restored.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

PIN = "a517b3846ee8457d84ee4975110bfda6797c44dc"
EGUI_PIN = "6d518fc799681571963842f95b55a6b68431b15a"
REMOTE = "https://github.com/storytold/winit.git"


def with_ime_api(android_mod: str) -> str:
    if "pub fn reset_ime_with_request" in android_mod or "pub fn reset_ime(" in android_mod:
        raise ValueError("Android IME API already changed; review the overlay")
    if "MotionAction::Scroll" not in android_mod or "MotionAction::HoverMove" not in android_mod:
        raise ValueError("Mouse/hover/scroll overlay is missing")
    anchor = "    pub fn set_ime_purpose(&self, _purpose: ImePurpose) {}\n"
    if android_mod.count(anchor) != 1:
        raise ValueError("Android winit IME insertion anchor changed")
    return android_mod.replace(
        anchor,
        anchor + "\n    pub fn reset_ime(&self) {}\n\n"
        "    #[inline]\n    pub fn reset_ime_with_request(&self, _request_id: u64) {}\n",
        1,
    )


def prepare(source: Path, builder_android: Path) -> None:
    raw = (source / "Cargo.toml").read_text()
    data = tomllib.loads(raw)
    if data["workspace"]["package"]["version"] != "0.15.0":
        raise ValueError("Only official PDFCraft v0.15.0 is supported")
    patches = data["patch"]["crates-io"]
    if patches["winit"].get("rev") != PIN or patches["winit"].get("git") != REMOTE:
        raise ValueError("PDFCraft official winit source pin changed")
    if patches["egui"].get("rev") != EGUI_PIN:
        raise ValueError("PDFCraft official egui source pin changed")
    vendor = source / "vendor" / "winit"
    if not vendor.is_dir():
        raise ValueError("Missing PDFCraft vendor/winit staging directory")
    overlay = with_ime_api((builder_android / "mod.rs").read_text())
    keycodes = (builder_android / "keycodes.rs").read_bytes()
    with tempfile.TemporaryDirectory(prefix=".pdfcraft-winit-", dir=vendor.parent) as temp:
        pinned = Path(temp) / "pinned"
        subprocess.run(["git", "init", "-q", str(pinned)], check=True)
        subprocess.run(
            ["git", "-C", str(pinned), "fetch", "--depth=1", REMOTE, PIN], check=True
        )
        subprocess.run(
            ["git", "-C", str(pinned), "checkout", "-q", "--detach", "FETCH_HEAD"], check=True
        )
        actual = subprocess.check_output(
            ["git", "-C", str(pinned), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != PIN:
            raise ValueError("Pinned Storytold winit commit did not match")
        if "ImeResetCompleted" not in (pinned / "src/event.rs").read_text():
            raise ValueError("Official winit missing IME completion event")
        if "pub fn reset_ime_with_request" not in (pinned / "src/window.rs").read_text():
            raise ValueError("Official winit missing IME reset API")
        if tomllib.loads((pinned / "Cargo.toml").read_text())["package"]["version"] != "0.30.13":
            raise ValueError("Pinned winit crate version changed")
        target = pinned / "src/platform_impl/android"
        (target / "mod.rs").write_text(overlay)
        (target / "keycodes.rs").write_bytes(keycodes)
        # Only the disposable candidate's generated source tree is replaced.
        shutil.rmtree(vendor)
        shutil.move(str(pinned), str(vendor))
    print("Pinned winit IME API restored with Android mouse/scroll/hover overlay")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: winit_v015_compat.py SOURCE_ROOT BUILDER_ANDROID_DIR")
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
