#!/usr/bin/env python3
"""Restore EXACT released VectorCraft .8 branding generation for .10, without touching master art.

The .9 producer skipped approved_branding.py install(), which added the original
regular/round adaptive icon resources AND native top-left in-app artwork for .8.
The audited .8 assets and hashes remain read-only. This script supplies only
monotonic .10 metadata in a disposable copy before executing the original hook.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

VERSION = "0.14.0-android.11"
VERSION_CODE = 16780811
PREVIOUS_CODE = 16780810
RELEASED_08_SOURCE = "07eed59ba0564ebcc199004248469d5a0f663340e0a46843552ca7261ce0892f"


def restore(builder: Path, checkout: Path) -> None:
    root = (checkout / "tools/approved-branding").resolve()
    config_file = root / "assets/manifest.json"
    original = json.loads(config_file.read_text())
    if (original.get("app"), original.get("package"), original.get("version_name"),
        original.get("version_code"), original.get("source_sha256")) != (
        "vectorcraft", "com.artcraft.vectorcraft", "0.14.0-android.8",
        16780808, RELEASED_08_SOURCE,
    ):
        raise RuntimeError("Original .8 approved VectorCraft icon source changed. Stop.")
    if not VERSION_CODE > PREVIOUS_CODE > original["version_code"]:
        raise RuntimeError("Non-monotonic Android version code. Stop.")

    with tempfile.TemporaryDirectory(prefix="vc-approved-08-to-10-") as temp:
        cloned = Path(temp) / "approved-branding"
        shutil.copytree(root, cloned)
        staged = dict(original)
        staged.update(version_name=VERSION, version_code=VERSION_CODE,
                      previous_version_code=PREVIOUS_CODE)
        (cloned / "assets/manifest.json").write_text(json.dumps(staged, indent=2) + "\n")
        # The actual .8 install() adds final resource + top-left UI branding
        # after Android project generation. The .9 build omitted this step.
        subprocess.run([sys.executable, str(cloned / "approved_branding.py"),
                        "install", str(builder.resolve()), "vectorcraft"], check=True)
        installed = json.loads(
            (builder / "tools/approved-branding/assets/manifest.json").read_text())
        assert installed["source_sha256"] == RELEASED_08_SOURCE
        assert installed["version_name"] == VERSION
        assert installed["version_code"] == VERSION_CODE
        assert installed["resources"] == original["resources"]
        assert installed["bg_color"] == original["bg_color"]
        print("PASS: installed exact .8 artwork/padding, round icons and in-app brand hook "
              "with v0.14.0-android.10 production metadata")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: restore_vectorcraft_08_branding.py BUILDER PUBLIC_CHECKOUT")
    restore(Path(sys.argv[1]), Path(sys.argv[2]))
