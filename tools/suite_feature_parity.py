#!/usr/bin/env python3
"""Fail-closed, read-only suite-wide PhotoCraft font/update feature contract.

Contract validation does NOT claim any app has passed device tests. For a
future per-app publisher, call require_release_parity(app, actual_evidence)
with evidence independently tied to the exact signed APK checksum. Any missing
or unverified feature blocks that application's promotion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATUS = {"not_verified","source_verified","artifact_verified","device_verified"}
FEATURE_IDS = (
    "custom_font_import","persistent_user_fonts","shared_font_folder",
    "font_refresh","font_menu_consistency","manual_update_check",
    "startup_update_opt_in","app_scoped_release_filter","updater_security",
    "update_menu_consistency","update_channel_selection",
)
APP_IDS = (
    "photocraft","vectorcraft","designcraft","filmcraft","pdfcraft",
    "wordcraft","deckcraft","effectcraft","lightcraft","soundcraft",
    "cadcraft","figcraft","gridcraft",
)


def read_contract(path: Path = ROOT / "configs/feature-parity.json") -> dict:
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1 or data.get("standard") != "artcraft-photocraft-font-and-update-parity-v1":
        raise ValueError("Unexpected ArtCraft feature-parity contract schema")
    if data.get("reference_app") != "photocraft":
        raise ValueError("PhotoCraft parity reference must not change without review")
    if set(data.get("expected_feature_ids",[])) != set(FEATURE_IDS) or len(data["expected_feature_ids"]) != len(FEATURE_IDS):
        raise ValueError("Missing or duplicate font/update requirements")
    apps = data.get("app_status",{})
    if set(apps) != set(APP_IDS):
        raise ValueError("Each of the 13 ArtCraft applications must be registered")
    for app, record in apps.items():
        actual = record.get("features",{})
        if set(actual) != set(FEATURE_IDS):
            raise ValueError(f"{app}: missing required font/update feature status")
        if any(v not in STATUS for v in actual.values()):
            raise ValueError(f"{app}: invalid unverified/verified status")
        digest = record.get("verified_apk_sha256")
        if digest is not None and not re.fullmatch(r"[a-f0-9]{64}",digest):
            raise ValueError(f"{app}: invalid signed APK evidence digest")
        if any(s == "device_verified" for s in actual.values()) and not digest:
            raise ValueError(f"{app}: device verification without exact signed APK checksum")
    if "Stable + Preview Releases" not in data.get("update_channels","") or "Exclude drafts" not in data["update_channels"]:
        raise ValueError("Missing stable/preview channel requirement")
    if data.get("update_startup") != "Optional persisted startup update check, initially OFF":
        raise ValueError("Startup update checks must be opt-in and off by default")
    if data.get("font_extensions") != [".ttf",".otf"]:
        raise ValueError("All Craft apps must support native TTF/OTF imports where text is available")
    if "read-only" not in data.get("shared_font_folder","") or "no all-files-access" not in data["shared_font_folder"]:
        raise ValueError("Shared folder must respect Android scoped storage")
    if "no silent install" not in data.get("update_integrity",""):
        raise ValueError("An updater cannot silently install packages")
    return data


def require_release_parity(app: str, apk_sha256: str, *, contract: dict | None = None) -> None:
    contract = contract if contract is not None else read_contract()
    entry = contract["app_status"].get(app)
    if entry is None:
        raise ValueError("Unknown Craft app")
    if not re.fullmatch(r"[a-f0-9]{64}", apk_sha256):
        raise ValueError("Signed release APK checksum is required")
    if entry["verified_apk_sha256"] != apk_sha256:
        raise ValueError("Feature evidence does not match the exact production-signed APK")
    missing = [k for k in FEATURE_IDS if entry["features"][k] != "device_verified"]
    if missing:
        raise ValueError(f"{app} font/update parity is not yet device-verified: {', '.join(missing)}")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", help="Specific app for per-release parity gating")
    parser.add_argument("--signed-apk-sha256",help="Exact signed APK SHA-256 for gating")
    args=parser.parse_args()
    data=read_contract()
    print(f"PASS: PhotoCraft parity contract complete for {len(data['app_status'])} apps, {len(FEATURE_IDS)} requirements.")
    if args.app or args.signed_apk_sha256:
        if not args.app or not args.signed_apk_sha256:
            parser.error("--app and --signed-apk-sha256 are required together")
        require_release_parity(args.app,args.signed_apk_sha256,contract=data)
        print("PASS: exact signed APK has verified font and update feature parity")
    else:
        print("No features or device tests are claimed passed. Publication is NOT authorized by this audit.")


if __name__=="__main__":
    main()
