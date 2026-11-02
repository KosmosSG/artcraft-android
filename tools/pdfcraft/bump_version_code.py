#!/usr/bin/env python3
"""Bump only PDFCraft's Android manifest versionCode (before re-signing).

cargo-apk2 derives versionCode from the three numeric semver components,
so 0.17.0-android.1 and 0.17.0-android.2 otherwise share a code.
The binary AndroidManifest.xml stores aapt2's integer value little-endian;
patch only the uniquely occurring 32-bit value, then align, sign and verify
in CI. Never edit an APK in place or treat the output as already signed.
"""
import argparse
from pathlib import Path
import struct
import zipfile

def rewrite(source: Path, dest: Path, old_code: int, new_code: int) -> None:
    assert old_code < new_code <= old_code + 4, "Only reviewed monotonic .android.2/.3/.4/.5 codes are authorized"
    assert source != dest
    old = struct.pack("<I", old_code)
    new = struct.pack("<I", new_code)
    with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(dest, "w") as outgoing:
        names = incoming.namelist()
        assert "AndroidManifest.xml" in names
        assert len(names) == len(set(names)), "APK has duplicate entries"
        for item in incoming.infolist():
            name = item.filename
            if name.upper().startswith("META-INF/"):
                continue  # An old JAR signature cannot survive manifest editing.
            data = incoming.read(item)
            if name == "AndroidManifest.xml":
                assert data.count(old) == 1, "Unexpected manifest versionCode encoding"
                assert data.count(new) == 0, "New version code already present"
                data = data.replace(old, new, 1)
            outgoing.writestr(item, data)
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(dest) as patched:
        for name in patched.namelist():
            if name != "AndroidManifest.xml":
                assert patched.read(name) == original.read(name), f"Changed payload: {name}"
        manifest = patched.read("AndroidManifest.xml")
        assert manifest.count(new) == 1 and manifest.count(old) == 0
    print(f"PASS: binary manifest versionCode {old_code} -> {new_code}; all other APK payload bytes unchanged")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("old_code", type=int)
    p.add_argument("new_code", type=int)
    args = p.parse_args()
    rewrite(args.source, args.destination, args.old_code, args.new_code)
