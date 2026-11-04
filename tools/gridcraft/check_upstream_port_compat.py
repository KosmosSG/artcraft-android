#!/usr/bin/env python3
"""Read-only report of tested v0.11.1 Android overlay anchors in newer upstream GridCraft."""
import argparse
import json
from pathlib import Path

ANCHORS = {
    "ribbon_extra_menu": (
        "crates/ui-egui/src/ribbon.rs",
        '            let more = icon_button(ui, Icon::More, t.text_dim, "More commands", vec2(26.0, ch));',
    ),
    "ribbon_font_dropdown": (
        "crates/ui-egui/src/ribbon.rs",
        '    let items: Vec<(&str, String)> = FONTS.iter().map(|f| (*f, f.to_string())).collect();',
    ),
    "font_scan_home": (
        "crates/ui-egui/src/fonts.rs",
        '                dirs.push(h.join(".local/share/fonts"));',
    ),
    "font_catalog_cache": (
        "crates/ui-egui/src/fonts.rs",
        "static CATALOG: OnceLock<Vec<Face>> = OnceLock::new();",
    ),
    "font_catalog_accessor": (
        "crates/ui-egui/src/fonts.rs",
        "pub fn catalog() -> &'static [Face] {",
    ),
    "font_binding_state": (
        "crates/ui-egui/src/lib.rs",
        "    fonts_seen: (u64, u64),",
    ),
    "android_saf_services": (
        "crates/ui-egui/src/lib.rs",
        "pub struct Services {",
    ),
    "sheet_app_state": (
        "crates/ui-egui/src/lib.rs",
        "pub struct SheetApp {",
    ),
    "sheet_app_logic": (
        "crates/ui-egui/src/lib.rs",
        "    pub fn logic(&mut self, ctx: &egui::Context) {",
    ),
    "save_changes_dialog": (
        "crates/ui-egui/src/dialogs.rs",
        '                "saveChanges" => {',
    ),
}

def audit(root: Path):
    outcomes = {}
    for name, (path, anchor) in ANCHORS.items():
        source = root / path
        count = source.read_text().count(anchor) if source.is_file() else 0
        outcomes[name] = {"path": path, "matches": count, "compatible": count == 1}
    changed = [name for name, value in outcomes.items() if not value["compatible"]]
    return {
        "target_upstream_tag": "v0.15.0",
        "android_tested_baseline": "gridcraft-v0.11.1-android.4-ctrlw-dcs-fix",
        "anchor_results": outcomes,
        "missing_or_changed_anchors": changed,
        "manual_port_required": bool(changed),
        "apk_compilation_verified": False,
        "signing_or_publication_authorized": False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_checkout", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    if not (args.upstream_checkout / "Cargo.toml").is_file():
        parser.error("GridCraft upstream source checkout not found")
    result = audit(args.upstream_checkout)
    report = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(report, end="")
    if args.output_json:
        args.output_json.write_text(report)
    if result["manual_port_required"]:
        print("::warning::GridCraft v0.15.0 changed tested Android overlay hooks. Manual adaptation and ARM64 compilation are required.")
    return 0  # Report only; CI success is NOT a working Android build.

if __name__ == "__main__":
    raise SystemExit(main())
