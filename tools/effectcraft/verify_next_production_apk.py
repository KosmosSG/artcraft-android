#!/usr/bin/env python3
"""Read-only, fail-closed verifier for the next production-signed EffectCraft APK.

Never reads, creates, exports or alters any keystore; does not sign or publish.
Only run on an actual locally available, independently production-signed APK.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import zipfile
from pathlib import Path

PACKAGE = "com.artcraft.effectcraft"
VERSION_NAME = "0.16.0-android.5"
VERSION_CODE = 16781317
# Certificate published with the owner's original, signed android.4 release.
PERMANENT_CERT_SHA256 = "10c93a0a55b9d66b6c64ac87372d5f3118c74a11c99fecb6e9f3951d2cbe8577"
PREVIOUS_APK_SHA256 = "9f034a891e03a1623479106c128a2a90aa45ef70e3c78a64437b78ae10820c12"


def check_signer(output: str) -> None:
    digests = re.findall(r"Signer #(\\d+) certificate SHA-256 digest: ([0-9a-fA-F:]+)", output)
    if len(digests) != 1 or digests[0][0] != "1":
        raise ValueError("Expected exactly one Android APK signer")
    digest = digests[0][1].replace(":", "").lower()
    if digest != PERMANENT_CERT_SHA256:
        raise ValueError("APK signer does not match the original EffectCraft certificate")


def check_badging(output: str) -> None:
    line = next((row for row in output.splitlines() if row.startswith("package:")), "")
    match = re.search(r"name='([^']+)' versionCode='(\\d+)' versionName='([^']+)'", line)
    if not match or match.group(1) != PACKAGE:
        raise ValueError("Incorrect package identity")
    if int(match.group(2)) != VERSION_CODE or match.group(3) != VERSION_NAME:
        raise ValueError("Incorrect or non-increasing EffectCraft release version")
    if "launchable-activity:" not in output:
        raise ValueError("Missing launchable Activity")


def verify(apk: Path, expected_sha256: str, apksigner: str, aapt: str) -> dict:
    if not apk.is_file() or apk.stat().st_size < 1_000_000:
        raise ValueError("Missing or implausibly small APK")
    actual = hashlib.sha256(apk.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256.lower()) or actual != expected_sha256.lower():
        raise ValueError("APK SHA-256 does not match the independently recorded candidate hash")
    if actual == PREVIOUS_APK_SHA256:
        raise ValueError("This is the old android.4 APK, not the next release")
    signing = subprocess.run([apksigner, "verify", "--verbose", "--print-certs", str(apk)],
                             text=True, capture_output=True, check=True)
    check_signer(signing.stdout)
    badging = subprocess.run([aapt, "dump", "badging", str(apk)],
                             text=True, capture_output=True, check=True)
    check_badging(badging.stdout)
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
    libs = [name for name in names if name.startswith("lib/") and name.endswith(".so")]
    if not libs or any(not name.startswith("lib/arm64-v8a/") for name in libs):
        raise ValueError("Missing ARM64 library or unexpected additional ABI")
    if not any(name.endswith(".dex") for name in names):
        raise ValueError("Java Activity DEX missing")
    return {"package": PACKAGE, "version_name": VERSION_NAME, "version_code": VERSION_CODE,
            "sha256": actual, "certificate_sha256": PERMANENT_CERT_SHA256,
            "native_libraries": len(libs)}


def self_test() -> None:
    certificate = "Signer #1 certificate SHA-256 digest: " + PERMANENT_CERT_SHA256
    check_signer(certificate)
    try:
        check_signer(certificate.replace(PERMANENT_CERT_SHA256, "0" * 64))
        raise AssertionError("Wrong signer was accepted")
    except ValueError:
        pass
    valid = "package: name='com.artcraft.effectcraft' versionCode='16781317' versionName='0.16.0-android.5'\\nlaunchable-activity: name='com.artcraft.effectcraft.EffectCraftActivity'"
    check_badging(valid)
    for broken in (valid.replace("16781317", "16781316"), valid.replace(PACKAGE, "com.test.effectcraft"),
                   valid.replace("0.16.0-android.5", "0.16.0-android.4")):
        try:
            check_badging(broken)
            raise AssertionError("Wrong identity/version accepted")
        except ValueError:
            pass
    print("PASS: offline release identity/signing guard self-tests (not APK validation)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path, nargs="?")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--apksigner", default="apksigner")
    parser.add_argument("--aapt", default="aapt")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.apk is None or not args.expected_sha256:
        parser.error("production APK and --expected-sha256 are both mandatory")
    import json
    print(json.dumps(verify(args.apk, args.expected_sha256, args.apksigner, args.aapt),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
