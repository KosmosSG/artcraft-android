#!/usr/bin/env python3
"""Fail-closed source preservation preflight for the PhotoCraft v0.19 Android port.

Validates the owner-tested Android v0.14.0-android.4 implementation, not the
runtime behavior of a compiled APK. No network, writes, or credentials.
"""
from pathlib import Path
import argparse
import re
import subprocess
import sys

BASELINE_COMMIT = "3af883c9db9d57d1b1641629707c2927176b484a"
UPSTREAM_TAG = "v0.20.1"
UPSTREAM_COMMIT = "327c4cc82e737a3e0af7c147a477126d77525495"
OWNER_APP_ID = "com.artcraft.photocraft"
OWNER_V2_SIGNER = "EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936"

ROOT = Path(__file__).resolve().parents[1]
PRESERVED_PATHS = (
    "adapters/photocraft/Cargo.toml",
    "adapters/photocraft/prepare.sh",
    "adapters/photocraft/src/lib.rs",
    "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java",
    "templates/android/ime_bridge.rs",
    "templates/android/system_fonts.rs",
    "templates/android/saf_bridge.rs",
    "templates/android/SafActivity.java",
    # The build bridge has branch-only launcher verification changes.
    # Check its required safeguards below, but do not require byte identity.
)
CHECKS = {
    "adapters/photocraft/Cargo.toml": (
        OWNER_APP_ID, 'java_sources = "java"', '"aarch64-linux-android"',
    ),
    "adapters/photocraft/src/lib.rs": (
        "app.set_wgpu(rs)", "renderer: eframe::Renderer::Wgpu",
        "self.ime.poll(raw)", "apply_android_modifiers",
        "system_fonts::install_system_fonts", "ai_menu::AndroidAiMenu",
        "write_mobile(", "commit_if_mapped",
    ),
    "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java": (
        "pcCommitIfMapped", "newStageFile(", 'stem + " (" + attempt + ")" + extension',
    ),
    "adapters/photocraft/prepare.sh": ("system_fonts.rs", "ime_bridge.rs"),
    "templates/android/ime_bridge.rs": ("ImeBridge",),
    "tools/photocraft_ai_fontscan_4g_stage.py": ("4",),
    "lib/build-common.sh": ("verify_android_bridge", "MAIN", "PhotoCraft"),
}
def die(message: str) -> None:
    raise SystemExit("FAIL PhotoCraft preservation gate: " + message)

def check_preservation() -> None:
    for relpath, tokens in CHECKS.items():
        path = ROOT / relpath
        if not path.is_file():
            die(f"Missing owner-tested component: {relpath}")
        contents = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in contents:
                die(f"Owner-tested component changed: {relpath} missing {token!r}")
    print("PASS: baseline app ID, font bridge, GPU, IME, AI, SAF and extension handling present")

def check_immutable_base() -> None:
    # Workflow fetches the protected release tag before invoking this check.
    command = ["git", "-C", str(ROOT), "diff", "--quiet",
               BASELINE_COMMIT, "HEAD", "--", *PRESERVED_PATHS]
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        die("core owner-tested adapter/runtime differs from the published release tag")
    print("PASS: critical preserved Android runtime files are byte-identical to release baseline")

def check_upstream(path: Path) -> None:
    if not (path / ".git").exists():
        die("missing isolated official Storytold checkout")
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    if result.stdout.strip() != UPSTREAM_COMMIT:
        die("upstream checkout does not match official pinned v0.20.1 commit")
    manifest = path / "Cargo.toml"
    if not manifest.exists():
        die("upstream checkout has no workspace manifest")
    if not (path / "crates" / "ui-egui").is_dir():
        die("upstream UI API not present; cannot attempt Android compilation")
    print(f"PASS: official upstream {UPSTREAM_TAG} exact commit {UPSTREAM_COMMIT}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-immutable-base", action="store_true")
    parser.add_argument("--upstream", type=Path)
    args = parser.parse_args()
    check_preservation()
    if args.check_immutable_base:
        check_immutable_base()
    if args.upstream is not None:
        check_upstream(args.upstream)
    print("NOTE: source checks are not APK, runtime, autosave or device validation.")

if __name__ == "__main__":
    main()
