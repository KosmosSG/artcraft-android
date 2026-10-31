#!/usr/bin/env python3
"""Read-only reference identity for a previously PUBLIC PhotoCraft release APK.

Never reads a private keystore, never signs an APK, and never alters a release.
A matching certificate proves APK update compatibility, not who owns a key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PACKAGE = "com.artcraft.photocraft"
TAG_PATTERN = re.compile(r"^photocraft-v[0-9]+\.[0-9]+\.[0-9]+-android\.[0-9]+$")
PACKAGE_PATTERN = re.compile(
    r"^package:\s+name='([^']+)'\s+versionCode='([0-9]+)'\s+versionName='([^']+)'",
    re.M,
)
# Android build-tools releases vary in whitespace and sometimes add trailing
# fields after the signer digest. Match the full SHA256 hex value while
# retaining strict validation of its length.
SIGNER_LINE_PATTERN = re.compile(
    # apksigner emits "Signer #1 certificate ..." or "V3.0 Signer:
    # certificate ..." for the actual published APK. Parse complete lines:
    # an unrecognized signer, malformed digest or trailing text must not be
    # silently ignored in a future multi-signer APK.
    r"^\s*(?:Signer\s+#(?P<signer_number>[0-9]+)|"
    r"V[1-4]\.0\s+Signer(?:\s+#(?P<scheme_signer_number>[0-9]+))?)"
    r":?\s+certificate\s+SHA-256\s+digest:\s*"
    r"(?P<digest>[a-fA-F0-9]{64})\s*$",
    re.I,
)


def parse_identity(badging: str, signing: str, tag: str) -> dict[str, object]:
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError("Unexpected PhotoCraft reference release tag")
    # aapt must describe exactly one package. Do not trust the first matching
    # substring if the output has duplicate, malformed, or conflicting lines.
    # This guards future tooling changes and accidental mixed APK metadata.
    package_lines = re.findall(r"^package:", badging, re.M)
    packages = PACKAGE_PATTERN.findall(badging)
    if len(package_lines) != 1 or len(packages) != 1:
        raise ValueError("aapt must report exactly one valid package/version line")
    # Count *all* certificate SHA256 records, including malformed or
    # unrecognized signer records. Previously a valid first signer could
    # hide an additional "Signer #2" or a truncated fingerprint.
    raw_signer_lines = [
        line for line in signing.splitlines()
        if re.search(r"\bcertificate\s+SHA-256\s+digest\b", line, re.I)
    ]
    signer_records = [SIGNER_LINE_PATTERN.fullmatch(line) for line in raw_signer_lines]
    if not raw_signer_lines or any(record is None for record in signer_records):
        raise ValueError("Unrecognized or malformed apksigner SHA-256 certificate record")
    if any(record.group("signer_number") not in (None, "1")
           or record.group("scheme_signer_number") not in (None, "1")
           for record in signer_records):
        raise ValueError("Unexpected additional APK signer")
    certificates = {record.group("digest").lower() for record in signer_records}
    if len(certificates) != 1:
        raise ValueError("APK reports multiple different signing certificates")
    certificate = certificates.pop()
    name, code, version = packages[0]
    if name != PACKAGE:
        raise ValueError("Reference APK has the wrong package ID")
    if version != tag.removeprefix("photocraft-v"):
        raise ValueError("Reference APK version does not match its release tag")
    if int(code) < 1:
        raise ValueError("Invalid production versionCode")
    return {
        "tag": tag,
        "package": name,
        "version_name": version,
        "version_code": int(code),
        "signer_certificate_sha256": certificate,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(apk: Path, aapt: Path, apksigner: Path, tag: str) -> dict[str, object]:
    if not apk.is_file() or apk.suffix.lower() != ".apk":
        raise ValueError("Reference APK is missing")
    for tool in (aapt, apksigner):
        if not tool.is_file():
            raise ValueError("Android build-tools executable is missing")
    subprocess.run([str(apksigner), "verify", "--verbose", str(apk)],
                   check=True, capture_output=True, text=True)
    badging = subprocess.check_output([str(aapt), "dump", "badging", str(apk)], text=True)
    signing = subprocess.check_output(
        [str(apksigner), "verify", "--print-certs", str(apk)], text=True
    )
    reference = parse_identity(badging, signing, tag)
    reference["apk_sha256"] = sha256_file(apk)
    reference["note"] = (
        "Read-only identity from public production release. NOT a signed AI "
        "candidate and NOT verification that a private signing key is available."
    )
    return reference


def self_test() -> None:
    tag = "photocraft-v0.14.0-android.1"
    badge = ("package: name='com.artcraft.photocraft' versionCode='16790004' "
             "versionName='0.14.0-android.1' platformBuildVersionName='15'\n")
    signer = "Signer #1 certificate SHA-256 digest: " + "Ab" * 32 + "\n"
    assert parse_identity(badge, "  " + signer + "Additional output\n", tag)["version_code"] == 16790004
    v3_signer = "V3.0 Signer: certificate SHA-256 digest: " + "Ab" * 32 + "\n"
    assert parse_identity(badge, v3_signer, tag)["signer_certificate_sha256"] == "ab" * 32
    # Multiple APK signing schemes using the same signer are legitimate.
    assert parse_identity(badge, signer + v3_signer, tag)["signer_certificate_sha256"] == "ab" * 32
    try:
        parse_identity(badge, signer + v3_signer.replace("Ab", "Cd"), tag)
    except ValueError:
        pass
    else:
        raise AssertionError("Accepted inconsistent signing certificates")
    parsed = parse_identity(badge, signer, tag)
    assert parsed["version_code"] == 16790004
    assert parsed["signer_certificate_sha256"] == "ab" * 32
    for wrong in (
        (badge.replace(PACKAGE, "com.artcraft.photocraft.ai.preview"), signer, tag),
        (badge.replace("0.14.0-android.1", "0.14.0-android.2"), signer, tag),
        (badge, signer, "v0.14.0"),
        (badge, "", tag),
        (badge + badge, signer, tag),
        (badge + "package: name='com.artcraft.photocraft'\n", signer, tag),
        (badge + badge.replace("16790004", "16790005"), signer, tag),
        ("note: " + badge, signer, tag),
        (badge, signer + "Signer #2 certificate SHA-256 digest: " + "Ab" * 32 + "\n", tag),
        (badge, signer + "V3.0 Signer #2: certificate SHA-256 digest: " + "Ab" * 32 + "\n", tag),
        (badge, signer + "Signer #1 certificate SHA-256 digest: " + "Ab" * 31 + "\n", tag),
        (badge, signer + "V3.0 Signer: certificate SHA-256 digest: " + "Ab" * 32 + "garbage\n", tag),
        (badge, signer + "Signer #1 certificate SHA-256 digest " + "Ab" * 32 + "\n", tag),
        (badge, signer + "Other Signer: certificate SHA-256 digest: " + "Ab" * 32 + "\n", tag),
    ):
        try:
            parse_identity(*wrong)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe public release identity was accepted")
    with tempfile.TemporaryDirectory() as root:
        p = Path(root) / "data.apk"
        p.write_bytes(b"identity-test")
        assert sha256_file(p) == hashlib.sha256(b"identity-test").hexdigest()
    print("PASS: package/version/tag/signing fingerprint parser and SHA256 contract")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--aapt", type=Path)
    parser.add_argument("--apksigner", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not all((args.apk, args.aapt, args.apksigner, args.tag, args.output)):
        parser.error("Reference APK, aapt, apksigner, tag and output must all be provided")
    report = inspect(args.apk, args.aapt, args.apksigner, args.tag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS: verified existing public PhotoCraft APK identity (read-only)")
    print("Reference package:", report["package"])
    print("Reference version:", report["version_name"], "code", report["version_code"])
    print("Reference certificate SHA256:", report["signer_certificate_sha256"])
    print("A future candidate must keep the package and certificate, and increase versionCode.")
    print("No candidate signed, private key read or release published.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"STOP: production reference identity verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
