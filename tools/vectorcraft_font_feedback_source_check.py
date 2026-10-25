#!/usr/bin/env python3
"""Fail-closed pinned-source guard for VectorCraft 0.14 notification Test APK.

ONLY the development/vectorcraft-v014-feedback-test-apk-20261024 branch is
permitted to produce a separately installed disposable-key Test APK.
No production keys, release publishing or automatic upstream synchronization.
"""
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = "https://github.com/storytold/vectorcraft"
SOURCE_SHA = "ad0566943ab9741e6356bbc9b53c3cc09895068d"
EXPECTED_REF = "refs/heads/fix/vectorcraft-v014-android8-feedback-20261025"


def insist(condition, detail):
    if not condition:
        raise ValueError(detail)


def git(root, *argv):
    return subprocess.check_output(
        ["git", "-C", str(root), *argv], text=True, stderr=subprocess.PIPE).strip()


def preflight():
    insist(os.environ.get("GITHUB_REF") == EXPECTED_REF,
           "Test APKs may only build on isolated review branch")
    adapter = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
    activity = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    manifest = tomllib.loads((ROOT / "adapters/vectorcraft/Cargo.toml").read_text())
    metadata = manifest["package"]["metadata"]["android"]
    insist(metadata["package"] == "com.artcraft.vectorcraft", "released package ID changed")
    insist(metadata["build_targets"] == ["aarch64-linux-android"], "ARM64 target changed")
    insist(metadata["sdk"]["min_sdk_version"] == 28, "minSdk changed")
    for marker in ("vcShowMessage", "vcRequestFontImport", "vcRefreshFontFolder",
                   "vcCheckForUpdates", "vcPollUpdateResult", "apply_android_modifiers",
                   "self.fonts.notice.take()", "vectorcraft.android.update_status",
                   "text.rescanFonts", "system_fonts::install_font_env"):
        insist(marker in adapter or marker in activity, "Android feature missing: " + marker)
    print("PASS: notification adapter, original production identity, original Font menu")


def verify_source(source):
    src = Path(source)
    insist((src / ".git").exists(), "expected an immutable upstream Git checkout")
    insist(git(src, "remote", "get-url", "origin").removesuffix(".git") == OFFICIAL,
           "unexpected upstream remote")
    insist(git(src, "rev-parse", "HEAD") == SOURCE_SHA, "upstream source SHA changed")
    workspace = tomllib.loads((src / "Cargo.toml").read_text())
    insist(workspace["workspace"]["package"]["version"] == "0.14.0",
           "workspace is not official v0.14.0")
    print("PASS: reviewed VectorCraft v0.14.0 official source")


def verify_port(source):
    verify_source(source)
    src = Path(source)
    menu = (src / "crates/ui-egui/src/menus.rs").read_text()
    for command in ("android.vectorcraft.fontImport",
                    "android.vectorcraft.fontFolder",
                    "android.vectorcraft.fontRefresh",
                    "android.vectorcraft.updates",
                    "android.vectorcraft.startupUpdates",
                    "android.vectorcraft.touchPad",
                    "android.vectorcraft.diagnostics"):
        insist(command in menu, "native menu command missing: " + command)
    crate = src / "apps/vectorcraft-android"
    manifest = tomllib.loads((crate / "Cargo.toml").read_text())
    metadata = manifest["package"]["metadata"]["android"]
    insist(metadata["package"] == "com.artcraft.vectorcraft.feedbacktest",
           "Test APK must not be production package")
    insist((crate / "src/lib.rs").is_file(), "Android Test launcher missing")
    insist("vcShowMessage" in (crate / "java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text(),
           "native Android Toast is missing")
    print("PASS: isolated candidate Android menu/Toast and package staging")


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (2, 3):
            raise ValueError("usage: source_check.py preflight|source|port [checkout]")
        if sys.argv[1] == "preflight":
            insist(len(sys.argv) == 2, "preflight needs no source path")
            preflight()
        elif sys.argv[1] == "source":
            insist(len(sys.argv) == 3, "source path required")
            preflight()
            verify_source(sys.argv[2])
        elif sys.argv[1] == "port":
            insist(len(sys.argv) == 3, "source path required")
            preflight()
            verify_port(sys.argv[2])
        else:
            raise ValueError("unknown command")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"STOP: read-only VectorCraft feedback Test gate failed: {exc}")
