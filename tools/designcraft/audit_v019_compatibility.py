#!/usr/bin/env python3
"""Fail-closed source audit before porting published DesignCraft Android features to official v0.19.0.

This does NOT implement the port, compile an APK, or confer release approval.
Usage: python3 tools/designcraft/audit_v019_compatibility.py PATH_TO_OFFICIAL_V019_CHECKOUT
"""
import json
import pathlib
import subprocess
import sys

UPSTREAM_SHA = "147b3f475056967353606b90fa0dc8bb39de7f27"
EXPECTED = {
    "crates/ui-egui/src/cursors.rs": ['mode_for(cfg!(target_arch = "wasm32"),'],
    "crates/ui-egui/src/theme.rs": ['let mut v = if t.dark { Visuals::dark() } else { Visuals::light() };'],
    "crates/ui-egui/src/canvas/input.rs": ['wheel_navigate(app, ui, resp, &xf);'],
    "crates/ui-egui/src/menus/ui_commands.rs": ['pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &['],
    "crates/ui-egui/src/menus/run.rs": [
        'fn run_ui_inner(app: &mut DesignApp, id: &str, p: &Value) -> Option<Result<Value, String>> {',
        'use super::export::{',
    ],
    "crates/fonts/src/fontdb/system.rs": [
        'dirs.extend(unix_font_dirs(home.as_deref(), xdg_data_home.as_deref()));'
    ],
}
PROTECTED_BUILDER_FILES = [
    "tools/designcraft/patch_v017_android.py",
    "tools/designcraft/patch_v017_interactions.py",
    "tools/designcraft/overlay_v017_cursor.py",
    "tools/designcraft/support/patch_launcher.py",
    "tools/designcraft/test_v017_published_preservation.py",
]

def audit(checkout, repo):
    findings = []
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = None
    findings.append({"check": "official-upstream-sha", "ok": sha == UPSTREAM_SHA, "actual": sha})
    for rel, anchors in EXPECTED.items():
        f = checkout / rel
        text = f.read_text(encoding="utf-8") if f.is_file() else ""
        for anchor in anchors:
            findings.append({
                "check": "source-anchor",
                "file": rel,
                "anchor": anchor[:90],
                "ok": text.count(anchor) == 1,
                "occurrences": text.count(anchor),
            })
    for rel in PROTECTED_BUILDER_FILES:
        findings.append({"check": "published-feature-source-present", "file": rel, "ok": (repo / rel).is_file()})
    return findings

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: audit_v019_compatibility.py OFFICIAL_V019_SOURCE_CHECKOUT")
    source = pathlib.Path(sys.argv[1]).resolve()
    repo = pathlib.Path(__file__).resolve().parents[2]
    results = audit(source, repo)
    print(json.dumps({"upstream": "storytold/designcraft", "tag": "v0.19.0", "checks": results}, indent=2))
    if not all(r["ok"] for r in results):
        sys.exit("BLOCKED: incompatible/unverified source or missing protected Android overlays; do not build.")
    print("Source anchors only: PASS. Port, tests, APK and device remain UNVERIFIED.")
