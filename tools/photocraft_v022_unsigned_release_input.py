#!/usr/bin/env python3
"""Prepare an UNSIGNED owner-approved PhotoCraft v0.22.0-android.3 production signing input.

Only run on the isolated GitHub Actions CI runner. The input APK is signed
with a throwaway builder key for compilation; its signature is removed by
rebuilding the ZIP records, then versionCode is patched in Android binary XML.
No private production signing key is touched. Fail closed on unknown layout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

PACKAGE = "com.artcraft.photocraft"
VERSION = "0.22.0-android.3"
TEST_CODE = 16782848
STABLE_CODE = 16790013
RELEASE_CODE = 16790014
V2_SHA256 = "edda8ab30390e383e10450193b8ae5864312a6ff80e9d6c7f3437816524e6936"
ANDROID_VERSION_CODE_RES_ID = 0x0101021B

def run(*cmd: str, check: bool = True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True)

def identity(apk: Path, aapt: Path) -> tuple[str, int, str]:
    data = run(str(aapt), "dump", "badging", str(apk)).stdout
    found = re.findall(
        r"^package:\s+name='([^']+)'\s+versionCode='(\d+)'\s+versionName='([^']+)'",
        data, re.MULTILINE,
    )
    if len(found) != 1:
        raise RuntimeError("Ambiguous or missing Android package/version fields")
    name, code, ver = found[0]
    return (name, int(code), ver)

def version_code_axml(raw: bytes, previous: int, target: int) -> bytes:
    """Modify only android:versionCode attribute's TYPE_INT data in binary XML."""
    data = bytearray(raw)
    if len(data) < 24:
        raise RuntimeError("Truncated binary AndroidManifest.xml")
    root_type, root_header, root_size = struct.unpack_from("<HHI", data, 0)
    if (root_type, root_header, root_size) != (0x0003, 8, len(data)):
        raise RuntimeError("Unrecognized Android binary XML header")
    resource_ids = []
    matches = 0
    pos = root_header
    while pos < len(data):
        if len(data) - pos < 8:
            raise RuntimeError("Truncated Android binary XML chunk")
        typ, header_size, size = struct.unpack_from("<HHI", data, pos)
        if header_size < 8 or size < header_size or pos + size > len(data):
            raise RuntimeError("Malformed Android binary XML chunk")
        if typ == 0x0180:
            if (size - header_size) % 4:
                raise RuntimeError("Malformed XML resource-map block")
            resource_ids = [
                struct.unpack_from("<I", data, p)[0]
                for p in range(pos + header_size, pos + size, 4)
            ]
        elif typ == 0x0102:
            # Android AXML ResXMLTree_node has a 16-byte chunk header
            # (8-byte ResChunk_header + lineNumber + comment). The 20-byte
            # ResXMLTree_attrExt follows that header; it is *not* part of
            # headerSize. The old >=36 test incorrectly rejected valid APKs.
            if header_size != 16 or size < 36:
                raise RuntimeError("Unsupported start-element chunk")
            attribute_start, attribute_size, attribute_count = struct.unpack_from("<HHH", data, pos + 24)
            if attribute_size != 20:
                raise RuntimeError("Unexpected Android XML attribute size")
            begin = pos + 16 + attribute_start
            if begin < pos + 36 or begin + attribute_size * attribute_count > pos + size:
                raise RuntimeError("Invalid manifest attribute positions")
            for off in range(begin, begin + attribute_size * attribute_count, attribute_size):
                name_index = struct.unpack_from("<I", data, off + 4)[0]
                if name_index >= len(resource_ids) or resource_ids[name_index] != ANDROID_VERSION_CODE_RES_ID:
                    continue
                typed_size, zero, kind, old = struct.unpack_from("<HBBI", data, off + 12)
                if (typed_size, zero, kind) != (8, 0, 0x10) or old != previous:
                    raise RuntimeError("Unexpected type/value for android:versionCode")
                struct.pack_into("<I", data, off + 16, target)
                matches += 1
        pos += size
    if pos != len(data) or matches != 1:
        raise RuntimeError(f"Expected one android:versionCode attribute, found {matches}")
    return bytes(data)

def self_test_axml() -> None:
    """Exercise the actual Android 16-byte start-element header layout."""
    resource_map = struct.pack("<HHII", 0x0180, 8, 12, ANDROID_VERSION_CODE_RES_ID)
    # ResXMLTree_node header(16) + ResXMLTree_attrExt(20) + one attribute(20).
    attribute = struct.pack("<IIIHBBI", 0, 0, 0xffffffff, 8, 0, 0x10, TEST_CODE)
    # The android:versionCode attr name is string-table index 0.
    attribute = attribute[:4] + struct.pack("<I", 0) + attribute[8:]
    node = (struct.pack("<HHIII", 0x0102, 16, 56, 1, 0xffffffff)
            + struct.pack("<IIHHHHHH", 0xffffffff, 0, 20, 20, 1, 0, 0, 0)
            + attribute)
    raw = struct.pack("<HHI", 3, 8, 8 + len(resource_map) + len(node)) + resource_map + node
    updated = version_code_axml(raw, TEST_CODE, RELEASE_CODE)
    assert len(updated) == len(raw)
    expected = raw[:-4] + struct.pack("<I", RELEASE_CODE)
    assert updated == expected, "Only versionCode data bytes may change"
    for old in (TEST_CODE - 1, RELEASE_CODE):
        try:
            version_code_axml(raw, old, RELEASE_CODE)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Accepted manifest with mismatched original versionCode")
    print("PASS: Android AXML start-element 16-byte header and versionCode patch")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--candidate", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--aapt", type=Path)
    p.add_argument("--apksigner", type=Path)
    p.add_argument("--zipalign", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    if args.self_test:
        self_test_axml()
        return
    if not all((args.candidate, args.output, args.aapt, args.apksigner, args.zipalign, args.report)):
        p.error("--candidate, --output, --aapt, --apksigner, --zipalign, --report are required")
    if not all(path.is_file() for path in (args.candidate, args.aapt, args.apksigner, args.zipalign)):
        raise RuntimeError("Required input APK/SDK tools are missing")
    expected = (PACKAGE, TEST_CODE, VERSION)
    if identity(args.candidate, args.aapt) != expected:
        raise RuntimeError(f"Wrong candidate identity: {identity(args.candidate, args.aapt)!r}")
    run(str(args.apksigner), "verify", "--verbose", str(args.candidate))
    cert_out = run(str(args.apksigner), "verify", "--print-certs", str(args.candidate)).stdout
    certs = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})", cert_out)
    if not certs or len(set(certs)) != 1 or certs[0].lower() == V2_SHA256:
        raise RuntimeError("Unexpected disposable signer: production key must not be used")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        repacked = Path(tmp) / "photocraft-unsigned-repacked.apk"
        names = set()
        with zipfile.ZipFile(args.candidate) as src, zipfile.ZipFile(repacked, "w") as dst:
            if src.testzip() is not None:
                raise RuntimeError("Candidate APK ZIP is corrupt")
            for info in src.infolist():
                if info.filename in names:
                    raise RuntimeError("Duplicate APK ZIP entry")
                names.add(info.filename)
                is_signer = (
                    info.filename.upper().startswith("META-INF/")
                    and (
                        info.filename.upper().endswith((".SF", ".RSA", ".DSA", ".EC"))
                        or info.filename.upper() == "META-INF/MANIFEST.MF"
                    )
                )
                if is_signer:
                    continue
                raw = src.read(info.filename)
                if info.filename == "AndroidManifest.xml":
                    raw = version_code_axml(raw, TEST_CODE, RELEASE_CODE)
                info.extra = b""
                info.comment = b""
                dst.writestr(info, raw)
        # zipalign is required before V2/V3 signing; do not re-align afterward.
        run(str(args.zipalign), "-f", "-p", "4", str(repacked), str(args.output))

    if identity(args.output, args.aapt) != (PACKAGE, RELEASE_CODE, VERSION):
        raise RuntimeError("Production unsigned APK package/versionCode failed")
    run(str(args.zipalign), "-c", "-p", "4", str(args.output))
    if run(str(args.apksigner), "verify", "--verbose", str(args.output), check=False).returncode == 0:
        raise RuntimeError("STOP: expected unsigned APK, got a valid signature")
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Corrupt unsigned ZIP")
        libs = [n for n in archive.namelist() if n.startswith("lib/") and n.endswith(".so")]
        if not libs or any(not n.startswith("lib/arm64-v8a/") for n in libs):
            raise RuntimeError("Unsigned candidate must contain ARM64-only libraries")
    metadata = {
        "kind": "UNSIGNED_PRODUCTION_V2_SIGNING_INPUT_ONLY",
        "package": PACKAGE,
        "versionName": VERSION,
        "versionCode": RELEASE_CODE,
        "stableVersionCode": STABLE_CODE,
        "requiredProductionCertificateSHA256": V2_SHA256,
        "initialDisposableSignerCertificateSHA256": certs[0].lower(),
        "unsignedAPK_SHA256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "unsignedAPK_sizeBytes": args.output.stat().st_size,
        "architecture": "arm64-v8a",
        "signed": False,
        "installable": False,
        "published": False,
        "nextStep": "Sign using ORIGINAL PhotoCraft V2 keystore then verify package, code, signer, and in-place device upgrade BEFORE publishing. Never use the ephemeral build key."
    }
    args.report.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print("PASS: production package/versionName and versionCode monotonicity")
    print("PASS: signing input ZIP integrity, ARM64-only libs, and zipalign")
    print("PASS: disposable signature removed (not installable or published)")
    print("Expected original V2 signer SHA-256:", V2_SHA256)
    print("VersionCode:", RELEASE_CODE)

if __name__ == "__main__":
    main()
