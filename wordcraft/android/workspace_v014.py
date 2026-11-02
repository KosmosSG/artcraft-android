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
    shell.write_text(code.replace(BUILDER_ANCHOR, SAFE_GUARD, 1), encoding="utf-8")
    print("WordCraft 0.14: preserved upstream arboard workspace dependency for Cargo resolution")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: workspace_v014.py <isolated pinned builder root>")
    apply(Path(sys.argv[1]).resolve())
