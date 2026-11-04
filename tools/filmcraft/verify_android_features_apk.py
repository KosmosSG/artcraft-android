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
import os
import subprocess
from pathlib import Path
import zipfile

NATIVE_COMMANDS = (
    b"android.filmcraft.importFont",
    b"android.filmcraft.sharedFonts",
    b"android.filmcraft.refreshFonts",
    b"app.checkForUpdates",  # single upstream Help entry, Android action 4
    b"android.filmcraft.startupUpdates",
    b"android.filmcraft.openRelease",
    b"android.filmcraft.buildInfo",
    b"filmcraft.android.menu.action",
    b"filmcraft.android.menu.status",
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
                     if re.fullmatch(r"classes(?:(?:[2-9]|[1-9][0-9]+))?\.dex", name)]
        if not dex_names:
            raise ValueError("Missing Java DEX bytecode")
        dex = b"".join(zipfile_obj.read(name) for name in dex_names)
    # Android versionName/versionCode are manifest properties, not native .so
    # literals. Verify the compiled APK using the pinned Android SDK rather
    # than expecting the version text in an optimized Rust shared library.
    sdk = Path(os.environ["ANDROID_HOME"])
    aapt2 = sdk / "build-tools" / "35.0.0" / "aapt2"
    if not aapt2.is_file():
        raise ValueError("Pinned Android SDK Build Tools 35.0.0 unavailable")
    badging = subprocess.check_output(
        [str(aapt2), "dump", "badging", str(apk)], text=True)
    identity = re.search(
        r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",
        badging, re.M)
    expected = ("com.artcraft.filmcraft", "1000005", "0.10.0-android.5")
    if identity is None or identity.groups() != expected:
        raise ValueError("FilmCraft compiled APK package/version mismatch")
    missing_native = [x.decode() for x in NATIVE_COMMANDS if x not in lib]
    missing_java = [x.decode() for x in JAVA_METHODS if x not in dex]
    if missing_native or missing_java:
        raise ValueError(f"Native FilmCraft commands missing: {missing_native}; "
                         f"Java Android feature methods missing: {missing_java}")
    return {"apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "package": expected[0], "versionCode": int(expected[1]),
            "version": expected[2],
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
