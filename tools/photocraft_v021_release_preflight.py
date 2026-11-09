#!/usr/bin/env python3
"""Read-only PhotoCraft Android.5 release preflight from the latest public stable APK.

Inputs are an EXISTING GitHub Release APK and standard Android SDK tools.
Never reads keystores, creates signatures, or publishes a release.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = "KosmosSG/artcraft-android"
STABLE_TAG = "photocraft-v0.20.2-android.2"
STABLE_PACKAGE = "com.artcraft.photocraft"
STABLE_VERSION = "0.20.2-android.2"
TEST_CANDIDATE_CODE = 16782592
PROPOSED_VERSION = "0.21.0-android.5"

def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apk", type=Path, required=True)
    p.add_argument("--aapt", type=Path, required=True)
    p.add_argument("--apksigner", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if not (args.apk.is_file() and args.aapt.is_file() and args.apksigner.is_file()):
        sys.exit("STOP: missing stable APK or Android SDK executable")
    with zipfile.ZipFile(args.apk) as archive:
        if archive.testzip() is not None:
            sys.exit("STOP: stable APK integrity check failed")
        native_libs = sorted(n for n in archive.namelist() if n.startswith("lib/") and n.endswith(".so"))
        if not native_libs or any(not name.startswith("lib/arm64-v8a/") for name in native_libs):
            sys.exit("STOP: stable APK ABI is not ARM64-only")
    run(str(args.apksigner), "verify", "--verbose", str(args.apk))
    badge = run(str(args.aapt), "dump", "badging", str(args.apk))
    matches = re.findall(r"^package:\s+name='([^']+)'\s+versionCode='(\d+)'\s+versionName='([^']+)'", badge, re.M)
    if len(matches) != 1:
        sys.exit("STOP: stable APK has ambiguous package identity")
    package, version_code, version_name = matches[0]
    if (package, version_name) != (STABLE_PACKAGE, STABLE_VERSION):
        sys.exit("STOP: stable APK package/version does not match expected public release")
    certs = run(str(args.apksigner), "verify", "--print-certs", str(args.apk))
    # The repository's reviewed parser accepts one certificate reported by
    # several APK signature schemes, but rejects a second signer or mismatch.
    from photocraft_ai_reference_signing import parse_identity
    verified = parse_identity(badge, certs, STABLE_TAG)
    stable_cert = str(verified["signer_certificate_sha256"])
    previous_code = int(verified["version_code"])
    required_code = max(previous_code, TEST_CANDIDATE_CODE) + 1
    if not (0 < required_code <= 2100000000):
        sys.exit("STOP: Android versionCode unavailable")
    report = {
        "source": "already published stable GitHub Release APK",
        "repository": REPO,
        "reference_tag": STABLE_TAG,
        "reference_package": package,
        "reference_version_name": version_name,
        "reference_version_code": previous_code,
        "reference_signer_certificate_sha256": stable_cert,
        "reference_apk_sha256": hashlib.sha256(args.apk.read_bytes()).hexdigest(),
        "reference_abis": ["arm64-v8a"],
        "candidate_version_name": PROPOSED_VERSION,
        "tested_isolated_candidate_version_code": TEST_CANDIDATE_CODE,
        "minimum_new_version_code": required_code,
        "production_package_required": STABLE_PACKAGE,
        "release_blocked": True,
        "reason": "Original V2 signing key must be available and used. The isolated test APK has a different package and disposable signature. A production candidate is not yet built or signed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS: verified published stable ARM64 package/signature and ZIP integrity")
    print("Reference versionCode:", previous_code)
    print("Minimum new versionCode:", required_code)
    print("Reference certificate SHA-256:", stable_cert)
    print("STOP: This job never signs/builds/publishes a production APK")

if __name__ == "__main__":
    main()
