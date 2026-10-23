#!/usr/bin/env python3
"""Fail-closed guard for the reviewed PhotoCraft v0.14 Android menu overlay.

The Android v0.14 migration inserts its menu items before build-common.sh.
That legacy builder must not reapply the v0.12 Custom Fonts patch afterward.
Only the immutable upstream v0.14.0 checkout with all six actions passes.
This script does not modify any file or request signing credentials.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

UPSTREAM = "https://github.com/storytold/photocraft"
TAG = "v0.14.0"
SHA = "ff4738810134d7f7e68b49f2e4f231b686282ff3"
IDS = (
    "window.artcraftCustomFonts",
    "window.artcraftSharedFontsSelect",
    "window.artcraftSharedFontsRefresh",
    "window.artcraftTouchShortcutPad",
    "help.artcraftUpdateSettings",
    "help.artcraftCheckUpdates",
)
EXPECTED_HOOKS = (
    "pub fn artcraft_shortcut_pad_allowed(",
    "pub fn artcraft_shortcut_pad_chrome_hidden(",
    "const CUSTOM_FONTS_ID:",
    "const SHORTCUT_PAD_ID:",
    "const CHECK_UPDATES_ID:",
    'egui::Id::new("artcraft.check_updates_requested")',
    '#[cfg(target_os = "android")]',
)


def validate_menu_text(menu: str) -> None:
    missing = [value for value in (*IDS, *EXPECTED_HOOKS) if value not in menu]
    if missing:
        raise ValueError("Android menu port missing: " + ", ".join(missing))
    if "pub fn is_enabled(app: &PhotocraftApp, id: &str) -> bool {" not in menu:
        raise ValueError("Upstream command enablement guard is missing")
    if "pub fn is_live(id: &str) -> bool {" not in menu:
        raise ValueError("Upstream live-command guard is missing")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


def validate_checkout(root: Path) -> None:
    if not (root / ".git").exists():
        raise ValueError("expected a checkout of official PhotoCraft")
    origin = git(root, "remote", "get-url", "origin").removesuffix(".git")
    if origin != UPSTREAM:
        raise ValueError("unexpected upstream repository: " + origin)
    if git(root, "rev-parse", "HEAD") != SHA:
        raise ValueError("wrong upstream source commit")
    if git(root, "rev-parse", f"{TAG}^{{commit}}") != SHA:
        raise ValueError("official tag does not resolve to reviewed commit")
    menu = root / "crates/ui-egui/src/menus.rs"
    validate_menu_text(menu.read_text(encoding="utf-8"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: photocraft_v014_menu_guard.py PINNED_PHOTOCRAFT_SOURCE")
    try:
        validate_checkout(Path(sys.argv[1]).resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"STOP: v0.14 Android menu compatibility was not proved: {error}")
    print("PASS: exact official PhotoCraft v0.14 checkout with all six Android menus")
