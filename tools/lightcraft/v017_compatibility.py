#!/usr/bin/env python3
"""Review-only v0.17 Android integration contract. Never builds, signs, or publishes.

Run after verify_v017_source.py has checked the exact official release tag.
The report distinguishes upstream API evidence from *unported* Android behavior.
"""
import argparse
import json
from pathlib import Path

EXPECTED_REF = "fbb4f66fcc868afdd8303d5227aa81db6a21d7fa"
LEGACY_SOURCE = "ec0cda9a6f320e3b32f659f16718f7bce6c3f12f"


def inspect(source: Path, builder: Path) -> dict:
    def contains(path: str, *anchors: str) -> bool:
        f = source / path
        if not f.is_file():
            return False
        text = f.read_text(encoding="utf-8")
        return all(anchor in text for anchor in anchors)

    def builder_contains(path: str, *anchors: str) -> bool:
        f = builder / path
        if not f.is_file():
            return False
        text = f.read_text(encoding="utf-8")
        return all(anchor in text for anchor in anchors)

    checks = {
        "lightcraft_app_public_api": contains(
            "crates/ui-egui/src/app.rs",
            "pub fn new(mut session: Session, services: Services)",
            "pub fn logic(&mut self, ctx: &egui::Context)",
            "pub fn ui(&mut self, ui: &mut egui::Ui)",
        ),
        "android_saf_services": contains(
            "crates/ui-egui/src/services.rs",
            "pub picker: Option<pick::Picker>",
            "pub pick_files: Option<PickFiles>",
            "pub pick_folder: Option<PickFolder>",
            "pub write: Option<WriteFn>",
            "pub write_shared: Option<SharedWrite>",
        ),
        "new_atomic_write_api": contains(
            "crates/ui-egui/src/services.rs", "pub write_new: Option<WriteFn>"
        ),
        "official_updates_command": contains(
            "crates/ui-egui/src/menus/ui_commands.rs",
            '"app.checkForUpdates"',
        ) and contains("crates/ui-egui/src/dialogs/updates_ui.rs", "craft_update"),
        "official_help_menu": contains(
            "crates/ui-egui/src/menus/menubar.rs",
            '"app.checkForUpdates"', '"app.about"',
        ),
        "original_lightcraft_android_saf_recipe": builder_contains(
            "lib/build-common.sh", '"lightcraft": {',
            "fn saf_write_and_commit(", "PickKind::Files", "PickKind::Save",
            "picker: Some(", "write: Some(",
        ),
        "android_touch_and_scroll_reference": builder_contains(
            "lib/build-common.sh", "scrolling.sh"
        ) and (builder / "lib/scrolling.sh").is_file(),
    }
    old_patch_layout_present = all(
        (source / path).is_file()
        for path in ("crates/ui-egui/src/panels/dialogs.rs",
                     "crates/ui-egui/src/menubar.rs")
    )
    missing = sorted(key for key, ok in checks.items() if not ok)
    blockers = [
        "Port Android Activity / SAF services to v0.17 module layout and audit write_new semantics.",
        "Replace v0.11-specific Help/About patch with v0.17 native checkForUpdates; verify app-specific release filtering.",
        "Reconcile egui/eframe 0.37 and Android winit/IME, touch, GPU, and adaptive cursor backends.",
        "Review session persistence/recovery and RAW/ICC/export/duplicate-name regressions.",
        "Compile and verify exact ARM64 candidate, original certificate identity and owner device tests.",
    ]
    if missing:
        blockers.insert(0, "Required upstream/reference code anchors missing: " + ", ".join(missing))
    if old_patch_layout_present:
        blockers.insert(0, "Unexpected legacy UI layout; reject automatic v0.17 port until reviewed.")
    return {
        "project": "LightCraft Android", "upstream_version": "0.17.0",
        "reference_builder_commit": EXPECTED_REF, "previous_android_source_commit": LEGACY_SOURCE,
        "checks": checks, "all_source_contracts_present": not missing and not old_patch_layout_present,
        "legacy_v011_ui_patch_compatible": False,
        "v017_android_port_complete": False, "arm64_apk_built": False,
        "production_signing_performed": False, "device_verified": False,
        "release_authorized": False, "release_blockers": blockers,
        "status": "SOURCE_API_REVIEW_ONLY__NO_ANDROID_APK",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path, help="Verified clean official v0.17.0 checkout")
    p.add_argument("builder", type=Path, help="Pinned MostafaXS1 Android reference checkout")
    p.add_argument("--report", type=Path, help="Optional JSON report destination")
    args = p.parse_args()
    report = inspect(args.source, args.builder)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if not report["all_source_contracts_present"]:
        raise SystemExit("STOP: v0.17 upstream/reference source contract drift")


if __name__ == "__main__":
    main()
