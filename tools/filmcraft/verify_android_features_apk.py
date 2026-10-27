#!/usr/bin/env python3
"""Fail-closed compiled APK audit for FilmCraft's Android File/Help integrations.

CI only; checks the *built* native .so and Java DEX rather than trusting staged
Python patch logs. Passing does not prove that the exact APK was installed,
screen-tested, GPU-accelerated or permanently signed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import zipfile

NATIVE_COMMANDS = (
    b"android.filmcraft.importFont",
    b"android.filmcraft.sharedFonts",
    b"android.filmcraft.refreshFonts",
    b"android.filmcraft.checkUpdates",
    b"android.filmcraft.startupUpdates",
    b"android.filmcraft.openRelease",
    b"android.filmcraft.buildInfo",
    b"filmcraft.android.menu.action",
    b"filmcraft.android.menu.status",
    b"0.10.0-android.2",
)
JAVA_METHODS = (
    b"fcRequestFontImport",
    b"fcRequestSharedFontFolder",
    b"fcRefreshSharedFonts",
    b"fcCheckForUpdates",
    b"fcSetStartupUpdatesEnabled",
    b"fcOpenUpdatePage",
    b"fcFeaturePoll",
)


def validate(apk: Path) -> dict:
    with zipfile.ZipFile(apk) as zipfile_obj:
        names = zipfile_obj.namelist()
        lib_names = [name for name in names if name.startswith("lib/arm64-v8a/")
                     and name.endswith(".so")]
        if not lib_names:
            raise ValueError("Missing ARM64 native library")
        lib = b"".join(zipfile_obj.read(name) for name in lib_names)
        dex_names = [name for name in names
                     if re.fullmatch(r"classes(?:[2-9][0-9]*)?\.dex", name)]
        if not dex_names:
            raise ValueError("Missing Java DEX bytecode")
        dex = b"".join(zipfile_obj.read(name) for name in dex_names)
    missing_native = [x.decode() for x in NATIVE_COMMANDS if x not in lib]
    missing_java = [x.decode() for x in JAVA_METHODS if x not in dex]
    if missing_native or missing_java:
        raise ValueError(f"Native FilmCraft commands missing: {missing_native}; "
                         f"Java Android feature methods missing: {missing_java}")
    return {"apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "compiled_android_menu": True,
            "native_commands": [x.decode() for x in NATIVE_COMMANDS],
            "java_methods": [x.decode() for x in JAVA_METHODS],
            "device_tested": False, "gpu_compositor_verified": False,
            "permanent_signing_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if not args.apk.is_file():
        raise SystemExit(f"Expected a built FilmCraft APK at {args.apk}")
    result = validate(args.apk)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "android-feature-compiled-audit.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print("PASS: FilmCraft ARM64 native File/Help menu commands and Android "
          "font/update Java bridge are embedded in the APK. "
          "Installation and device functionality are not yet verified.")


if __name__ == "__main__":
    main()
