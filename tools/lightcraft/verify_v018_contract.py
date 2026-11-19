#!/usr/bin/env python3
"""Read-only upstream v0.18.0 LightCraft Android API gate; DOES NOT build an APK.

Usage: python3 tools/lightcraft/verify_v018_contract.py SOURCE BUILDER SUITE
Use --require-android-port before any expensive candidate build: it fails closed
while the mandatory Android compatibility work remains incomplete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_commit(root: Path, expected: str, name: str) -> None:
    commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if commit != expected:
        raise ValueError(f"{name}: expected immutable commit {expected}; got {commit}")
    for args in (["diff", "--quiet", "HEAD", "--"], ["diff", "--cached", "--quiet", "--"]):
        if subprocess.run(["git", "-C", str(root), *args], check=False).returncode:
            raise ValueError(f"{name}: tracked checkout has changes")


def has_all(path: Path, anchors: tuple[str, ...]) -> bool:
    return path.is_file() and all(item in path.read_text(encoding="utf-8") for item in anchors)


def inspect(source: Path, builder: Path, suite: Path, lock: dict) -> dict:
    if lock["application"] != "lightcraft":
        raise ValueError("Refusing cross-app configuration")
    upstream = lock["upstream"]
    checked_commit(source, upstream["tag_commit"], "upstream")
    cargo = tomllib.loads((source / "Cargo.toml").read_text(encoding="utf-8"))
    workspace = cargo["workspace"]["package"]
    if (workspace["version"], workspace["rust-version"]) != (
        upstream["workspace_version"], upstream["rust_msrv"]
    ):
        raise ValueError("Upstream Cargo version or Rust MSRV changed")
    if "0.37" not in str(cargo["workspace"]["dependencies"]["egui"]):
        raise ValueError("Unexpected egui version; review UI bridge before compile")
    icon = lock["approved_icon"]
    if sha256(suite / icon["path"]) != icon["sha256"]:
        raise ValueError("Owner-approved LightCraft icon does not match protected hash")

    checks = {
        "modern_app_api": has_all(
            source / "crates/ui-egui/src/app.rs",
            ("pub fn new(mut session: Session, services: Services)", "pub fn ui(&mut self, ui: &mut egui::Ui)"),
        ),
        "saf_pickers_and_callbacks": has_all(
            source / "crates/ui-egui/src/services.rs",
            ("pub picker: Option<pick::Picker>", "pub pick_files: Option<PickFiles>",
             "pub pick_folder: Option<PickFolder>", "pub write: Option<WriteFn>",
             "pub write_new: Option<WriteFn>", "pub write_shared: Option<SharedWrite>"),
        ),
        "official_update_command": has_all(
            source / "crates/ui-egui/src/menus/ui_commands.rs",
            ('"app.checkForUpdates"',),
        ),
        "native_update_dialog": (source / "crates/ui-egui/src/dialogs/updates_ui.rs").is_file(),
        "saf_builder_preserved": has_all(
            builder / "lib/build-common.sh",
            ('"lightcraft": {', "fn saf_write_and_commit(", "PickKind::Files",
             "PickKind::Save", "picker: Some(", "write: Some("),
        ),
        "legacy_android_integration_preserved": (
            (suite / "tools/lightcraft/apply_android_fixes.py").is_file()
            and (suite / "tools/lightcraft/lightcraft_updates.java.inc").is_file()
            and (suite / "tools/lightcraft/lightcraft_updates.rs").is_file()
        ),
    }
    missing = sorted(k for k, valid in checks.items() if not valid)
    port_ready = bool(lock["gates"]["android_api_port_complete"])
    return {
        "application": "lightcraft",
        "upstream_tag": upstream["stable_tag"],
        "upstream_commit": upstream["tag_commit"],
        "source_contract_checks": checks,
        "source_contract_verified": not missing,
        "missing": missing,
        "android_api_port_complete": port_ready,
        "arm64_apk_built": False,
        "temporary_apk_signature_verified": False,
        "production_signing_performed": False,
        "release_published": False,
        "status": "SOURCE_REVIEW_ONLY__NO_ANDROID_APK" if not port_ready
                  else "SOURCE_CHECKED__ANDROID_PORT_REQUIRES_BUILD_VALIDATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("builder", type=Path)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--require-android-port", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    lock_file = args.suite / "configs/upstream/lightcraft-v018.json"
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
    report = inspect(args.source, args.builder, args.suite, lock)
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    if not report["source_contract_verified"]:
        raise SystemExit("STOP: upstream Android contract drift: " + ", ".join(report["missing"]))
    if args.require_android_port and not report["android_api_port_complete"]:
        raise SystemExit("STOP: port of approved LightCraft Android SAF/UI/updater not complete")


if __name__ == "__main__":
    main()
