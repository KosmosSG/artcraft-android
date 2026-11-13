#!/usr/bin/env python3
"""Read-only compatibility probe for pinned GridCraft 0.19.1 Android integration.

This is NOT a build approval or proof that an Android overlay compiles.
"""
import argparse
import json
import subprocess
import tomllib
from pathlib import Path

UPSTREAM_SHA = "476448d7d9f3a5f8e93fcf7d98b47fd52293fe7f"
ANCHORS = {
    "crates/ui-egui/src/ribbon/title_bar.rs": [
        "            ui.add_space(TITLE_LEFT_PAD);",
        'let more = icon_button(ui, Icon::More',
    ],
    "crates/ui-egui/src/ribbon/home.rs": [
        "let items: Vec<(&str, String)> = FONTS.iter()",
    ],
    "crates/ui-egui/src/fonts.rs": ['dirs.push(h.join(".local/share/fonts"));'],
    "crates/ui-egui/src/lib.rs": ["pub struct SheetApp {", "fonts_seen: (u64, u64),"],
    "crates/ui-egui/src/app.rs": [
        "fonts_seen: (0, 0),",
        "pub fn logic(&mut self, ctx: &egui::Context) {",
    ],
    "crates/ui-egui/src/app/fonts.rs": [
        "let seen = self.fonts_key();",
        "if used == self.fonts_bound {",
    ],
    "crates/ui-egui/src/services.rs": ["pub struct Services {"],
    "crates/ui-egui/src/app/quit.rs": [
        "SaveAnswer::Save => {",
        "File operations include the cell still being edited",
    ],
    "crates/ui-egui/src/dialogs/show.rs": ["Don't Save", "answer_save_changes"],
    "crates/ui-egui/src/app/commands.rs": ["pub(super) fn alert(&mut self, e: String)"],
}


def audit(source: Path, check_commit: bool) -> dict:
    manifest = tomllib.loads((source / "Cargo.toml").read_text())
    pkg = manifest["workspace"]["package"]
    failures = []
    if pkg["version"] != "0.19.1":
        failures.append("Workspace version mismatch")
    if pkg.get("rust-version") != "1.95":
        failures.append("Rust version requirement mismatch")
    if check_commit:
        try:
            sha = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
            ).strip()
            if sha != UPSTREAM_SHA:
                failures.append("Pinned upstream SHA mismatch: " + sha)
        except (OSError, subprocess.CalledProcessError):
            failures.append("Cannot verify upstream commit")
    paths = {}
    for name, anchors in ANCHORS.items():
        path = source / name
        if not path.is_file():
            failures.append("Missing file: " + name)
            paths[name] = {"exists": False}
            continue
        data = path.read_text()
        counts = {anchor: data.count(anchor) for anchor in anchors}
        paths[name] = {"exists": True, "anchor_counts": counts}
        for anchor, count in counts.items():
            if count != 1:
                failures.append(f"{name}: anchor count {count}: {anchor[:70]}")
    return {
        "upstream_sha": UPSTREAM_SHA,
        "anchor_probe_passed": not failures,
        "failures": failures,
        "paths": paths,
        "android_source_port_complete": False,
        "compiled_apk_verified": False,
        "production_signing_authorized": False,
        "production_package_unchanged": "com.artcraft.gridcraft",
        "side_by_side_test_package": "com.artcraft.gridcraft.candidate",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_checkout", type=Path)
    parser.add_argument("--skip-sha-check", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(args.upstream_checkout, not args.skip_sha_check)
    except (OSError, ValueError, KeyError) as exc:
        result = {"anchor_probe_passed": False, "failures": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["anchor_probe_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
