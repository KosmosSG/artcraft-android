#!/usr/bin/env python3
"""Convert a disposable copy of the *published* DesignCraft v0.17 builder to v0.20.1.

This is only for an isolated CI workspace, never the protected repository checkout.
Fail closed if any assumed upstream metadata/patch point has changed.
"""
from pathlib import Path
import json
import sys

OLD_SHA = "16322ad54b3a20b4cd70666be7431086514d0a36"
NEW_SHA = "33a467872268c98536231491865b4011b0275b17"
NEW_VERSION = "0.20.1-android.1"

def exactly(src, old, new, label, count=1):
    actual = src.count(old)
    if actual != count:
        raise ValueError(f"{label}: expected {count} occurrences, got {actual}: {old!r}")
    return src.replace(old, new)

def main(root):
    manifest = root / "configs/upstream/designcraft-v017.json"
    obj = json.loads(manifest.read_text())
    if obj.get("stable_tag") != "v0.17.2" or obj.get("tag_commit") != OLD_SHA:
        raise ValueError("Published DesignCraft v0.17.2 source lock has changed")
    obj["stable_tag"] = "v0.20.1"
    obj["tag_commit"] = NEW_SHA
    obj["upstream_workspace_version"] = "0.20.1"
    obj["integration_status"] = "isolated-v0201-unverified-android-test"
    obj["test_version"] = NEW_VERSION
    obj["android_source_port_complete"] = False
    obj["android_build_verified"] = False
    obj["permanent_signing_authorized"] = False
    obj["production_release_authorized"] = False
    manifest.write_text(json.dumps(obj, indent=2) + "\n")
    builder = root / "lib/build-common.sh"
    s = builder.read_text()
    s = exactly(s, '"v0.17.2"', '"v0.20.1"', "tag in provenance checker")
    s = exactly(s, '"0.17.2"', '"0.20.1"', "workspace version in provenance checker")
    s = exactly(s, "git clone --depth 1 --branch v0.17.2", "git clone --depth 1 --branch v0.20.1", "pinned checkout")
    s = exactly(s, 'APP_VERSION="0.17.2-android.5"', f'APP_VERSION="{NEW_VERSION}"', "test APK filename")
    builder.write_text(s)
    overlay = root / "tools/designcraft/patch_v017_android.py"
    o = overlay.read_text()
    o = exactly(o, 'candidate_version = "0.17.2-android.5"', f'candidate_version = "{NEW_VERSION}"', "test manifest version")
    overlay.write_text(o)
    print(f"Prepared isolated, fail-closed DesignCraft v0.20.1 test builder ({NEW_VERSION}); original release unaffected")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_v0201_test_builder.py ISOLATED_COPY")
    root = Path(sys.argv[1]).resolve()
    if not (root / "build-debug.sh").is_file():
        raise SystemExit("Expected a disposable copy of the Android builder")
    if root == Path.cwd().resolve():
        raise SystemExit("Refusing to rewrite the checked-out integration branch")
    main(root)
