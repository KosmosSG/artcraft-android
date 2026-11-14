#!/usr/bin/env python3
"""Read-only LightCraft v0.20 Android upstream source preflight.

Never modifies the published app, upstream checkout, or builder.
Must run before an ARM64 build; fails closed on wrong tag/source/API.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXPECTED_BASE = "1cf18815195c640b28dfd50410ae112a8975c8b4"
EXPECTED_UPSTREAM = "192ff72923c39e6623f2c7ff67ab3a119deb8071"
BASE_TAG = "lightcraft-v0.18.0-android.1"
BRANCH = "integration/lightcraft-upstream-20261110"

class GateError(RuntimeError):
    pass

def git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    if result.returncode:
        raise GateError(f"Git check failed ({' '.join(args)}): {result.stderr.strip()[:300]}")
    return result.stdout.strip()

def demand(test, message):
    if not test:
        raise GateError(message)

def run(suite, source):
    suite = suite.resolve()
    source = source.resolve()
    demand(suite != source, "source must be a separate immutable checkout")
    manifest_path = suite / "configs/upstream/integration-20261110-lightcraft.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    demand(manifest["protected_android_baseline"] == BASE_TAG, "baseline identifier changed")
    demand(manifest["target_upstream_tag"] == "v0.20.0", "upstream tag changed")
    demand(manifest["target_upstream_commit"] == EXPECTED_UPSTREAM, "upstream pin changed")
    demand(not manifest["production_signing_authorized"], "production signing permission must be false")
    demand(not manifest["publishing_authorized"], "publishing permission must be false")
    demand(git(suite, "rev-parse", f"{BASE_TAG}^{{commit}}") == EXPECTED_BASE, "published tag no longer matches known baseline")
    demand(git(suite, "merge-base", EXPECTED_BASE, "HEAD") == EXPECTED_BASE, "working branch is not descended from published baseline")
    demand(git(source, "rev-parse", "HEAD") == EXPECTED_UPSTREAM, "upstream checkout SHA mismatch")
    demand(not git(source, "status", "--porcelain", "--untracked-files=no"), "upstream checkout has tracked modifications")
    cargo = (source / "Cargo.toml").read_text(encoding="utf-8")
    demand(re.search(r'(?m)^version\s*=\s*"0\.20\.0"\s*$', cargo) is not None, "upstream workspace version mismatch")
    demand(re.search(r'(?m)^rust-version\s*=\s*"1\.95"\s*$', cargo) is not None, "unexpected Rust MSRV")
    demand(re.search(r'(?m)^wgpu\s*=\s*\{\s*version\s*=\s*"30"', cargo) is not None, "unexpected wgpu API")
    demand(re.search(r'(?m)^egui\s*=\s*\{\s*version\s*=\s*"0\.37"', cargo) is not None, "unexpected egui API")
    for rel in ("crates/ui-egui/src/menus/menubar.rs", "crates/ui-egui/src/menus/run.rs",
                "crates/ui-egui/src/dialogs.rs", "crates/gpu/src/render.rs",
                "crates/engine/src/lightroom_catalog.rs"):
        demand((source / rel).is_file(), f"required upstream source missing: {rel}")
    # Explicitly block accidentally using the v0.18-only compile workflow as a v0.20 build.
    old = (suite / ".github/workflows/lightcraft-v018-arm64-test.yml").read_text(encoding="utf-8")
    demand("32d569ad5d19a6b55cf8d5c077127faa0f44a83b" in old,
           "legacy test workflow changed: review separately")
    print("PASS: LightCraft v0.20 source provenance, published ancestry, dependency/API preflight")
    print("STOP GATE: this is NOT v0.20 Android port or APK validation")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suite", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    a = p.parse_args()
    try:
        run(a.suite, a.source)
    except (GateError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"FAIL CLOSED: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
