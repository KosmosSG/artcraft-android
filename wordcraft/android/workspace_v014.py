#!/usr/bin/env python3
"""Protect WordCraft v0.14 Cargo workspace dependency from the older builder.

The reference builder's arboard vendoring regex removes *every* arboard
assignment, including [workspace.dependencies], leaving cargo metadata broken.
For this pinned upstream trial, retain the official arboard resolver entry;
do not silently invent a 3.7-compatible version of the reference 3.6 stub.
"""
from pathlib import Path
import sys

OFFICIAL = 'arboard = { version = "3.7", default-features = false, features = ["wayland-data-control"] }'
BUILDER_ANCHOR = r"""if grep -rqE '\barboard\b' "$SRC"/crates/*/src 2>/dev/null; then"""
SAFE_GUARD = r"""if [[ "$APP" != "wordcraft" ]] && grep -rqE '\barboard\b' "$SRC"/crates/*/src 2>/dev/null; then"""


def apply(builder: Path) -> None:
    upstream = builder / "source/wordcraft/Cargo.toml"
    shell = builder / "lib/build-common.sh"
    if upstream.read_text(encoding="utf-8").count(OFFICIAL) != 1:
        raise ValueError("Expected pinned upstream 0.14 arboard workspace dependency is absent")
    code = shell.read_text(encoding="utf-8")
    if code.count(BUILDER_ANCHOR) != 1:
        raise ValueError("Pinned builder arboard hook changed; stop before deleting workspace dependency")
    code = code.replace(BUILDER_ANCHOR, SAFE_GUARD, 1)
    code = preserve_egui_winit_and_winit(code, upstream.read_text(encoding="utf-8"))
    shell.write_text(code, encoding="utf-8")
    print("WordCraft 0.14: preserved upstream arboard and Storytold egui/winit 0.37 IME APIs")


# WordCraft 0.14.0 uses the Storytold-pinned egui 0.37 and winit fork.
# The reference builder's egui-winit 0.36.2 and winit 0.30.13 vendor copies
# are not interchangeable with the upstream IME request/acknowledgement APIs.
PINNED_WIN = 'winit = { git = "https://github.com/storytold/winit.git", rev = "a517b3846ee8457d84ee4975110bfda6797c44dc" }'
OLD_EGUI_DEP = 'egui-winit = "0.36"'
OLD_EGUI_REG = '    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());'
EGUI_VENDOR_START = 'echo "Vendoring the Android-compatible egui-winit for $TITLE (system clipboard via JNI)..."'
EGUI_VENDOR_END = '# Some apps call `rfd` directly from a crate that ends up in the launcher'
WINIT_VENDOR_START = 'echo "Vendoring the mouse/scroll-aware winit for $TITLE..."'
WINIT_VENDOR_END = "# Every launcher uses the builder's vendored android-activity"


def exactly_one(haystack: str, needle: str, description: str) -> None:
    found = haystack.count(needle)
    if found != 1:
        raise ValueError(f"{description}: expected one anchor, got {found}")


def guard_vendor_block(code: str, begin: str, finish: str, description: str) -> str:
    exactly_one(code, begin, description + " begin")
    exactly_one(code, finish, description + " end")
    start = code.index(begin)
    stop = code.index(finish)
    if stop <= start:
        raise ValueError(description + " order changed")
    code = code[:start] + 'if [[ "$APP" != "wordcraft" ]]; then\n' + code[start:]
    finish_index = code.index(finish)
    return code[:finish_index] + "fi\n\n" + code[finish_index:]


def preserve_egui_winit_and_winit(code: str, upstream_manifest: str) -> str:
    exactly_one(upstream_manifest, PINNED_WIN, "Storytold 0.14 winit fork")
    # Do not shadow the 0.37 source fork with the older 0.36 vendored crate.
    code = guard_vendor_block(code, EGUI_VENDOR_START, EGUI_VENDOR_END, "egui-winit vendoring")
    code = guard_vendor_block(code, WINIT_VENDOR_START, WINIT_VENDOR_END, "winit vendoring")
    # The generated launcher must resolve egui-winit 0.37 from the pinned fork.
    exactly_one(code, OLD_EGUI_DEP, "launcher egui-winit 0.36 dependency")
    code = code.replace(OLD_EGUI_DEP,
                        'egui-winit = "{\'0.37\' if app == \'wordcraft\' else \'0.36\'}"', 1)

    # The vendored 0.36 JNI registration is not an API in Storytold's 0.37.
    exactly_one(code,
                "    if saf:\n        entry = f'''//! Generated Android launcher for {title}.",
                "launcher entrypoint anchor")
    code = code.replace(
        "    if saf:\n        entry = f'''//! Generated Android launcher for {title}.",
        '    egui_android_registration = ("" if app == "wordcraft" else '
        '"    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());")\n'
        "    if saf:\n        entry = f'''//! Generated Android launcher for {title}.", 1)
    if code.count(OLD_EGUI_REG) != 3:
        # One in the generated conditional above and two in the entry templates.
        raise ValueError("Android 0.36 activity-registration API layout changed")
    before, divider, after = code.partition("    if saf:\n        entry = f'''")
    if not divider or after.count(OLD_EGUI_REG) != 2:
        raise ValueError("Expected exactly two launcher-template registration sites")
    code = before + divider + after.replace(OLD_EGUI_REG, "{egui_android_registration}")
    return code


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: workspace_v014.py <isolated pinned builder root>")
    apply(Path(sys.argv[1]).resolve())
