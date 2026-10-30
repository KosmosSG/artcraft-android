#!/usr/bin/env python3
"""Fail-closed, read-only compatibility gate for a FUTURE PhotoCraft AI APK.

The program reads two already-built Android APK files, uses SDK aapt and
apksigner to verify them, and compares release identity. It NEVER builds,
signs, installs, merges, uploads or publishes an app. The reference must be
the original publicly released PhotoCraft APK, not an arbitrary preview.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from photocraft_ai_reference_signing import inspect as inspect_apk

PUBLIC_TAG = "photocraft-v0.14.0-android.1"
PUBLIC_VERSION_CODE = 16790004
PUBLIC_SIGNER_SHA256 = (
    "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"
)
PUBLIC_PACKAGE = "com.artcraft.photocraft"
CANDIDATE_TAG_PATTERN = re.compile(
    r"^photocraft-v(\d+)\.(\d+)\.(\d+)-android\.(\d+)$"
)


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def release_key(tag: str) -> tuple[int, int, int, int]:
    match = CANDIDATE_TAG_PATTERN.fullmatch(tag)
    ensure(match is not None, "Candidate requires a PhotoCraft-specific Android release tag")
    return tuple(int(group) for group in match.groups())


def check_candidate(
    reference: dict[str, object], candidate: dict[str, object],
    candidate_badging: str,
) -> dict[str, object]:
    """Validate package, certificate, version ordering and launcher identity.

    Both dictionaries MUST come from inspect_apk(), which verifies actual APK
    signatures. Synthetic dictionaries are used by offline unit tests only.
    """
    ensure(reference.get("tag") == PUBLIC_TAG,
           "Reference must be the publicly released PhotoCraft 0.14.0-android.1")
    ensure(reference.get("package") == PUBLIC_PACKAGE,
           "Reference package does not match production PhotoCraft")
    ensure(reference.get("version_code") == PUBLIC_VERSION_CODE,
           "Reference versionCode differs from published PhotoCraft")
    ensure(reference.get("signer_certificate_sha256") == PUBLIC_SIGNER_SHA256,
           "Reference signer certificate differs from published PhotoCraft")
    ensure(candidate.get("package") == PUBLIC_PACKAGE,
           "Candidate package differs: a preview APK cannot update PhotoCraft")
    ensure(candidate.get("signer_certificate_sha256") == PUBLIC_SIGNER_SHA256,
           "Candidate must be signed with the original PhotoCraft production certificate")
    ensure(isinstance(candidate.get("version_code"), int)
           and not isinstance(candidate["version_code"], bool)
           and candidate["version_code"] > PUBLIC_VERSION_CODE,
           "Candidate versionCode must be strictly above the installed public version")
    candidate_tag = candidate.get("tag")
    ensure(isinstance(candidate_tag, str), "Missing candidate Android release tag")
    ensure(release_key(candidate_tag) > release_key(PUBLIC_TAG),
           "Candidate versionName must be newer than the current public release")
    ensure(candidate.get("version_name") == candidate_tag.removeprefix("photocraft-v"),
           "Candidate APK versionName must match the proposed PhotoCraft release tag")
    # Check the independent aapt output against the already signature-verified
    # inspect_apk() result. Previously a stale/contradictory badging string
    # could pass source-level tests despite mismatched version/package fields.
    # The CLI uses one actual APK for both reads, but this extra fail-closed
    # invariant catches tool output corruption and future integration mistakes.
    badges = re.findall(
        r"^package:\s+name='([^']+)'\s+versionCode='([0-9]+)'\s+versionName='([^']+)'",
        candidate_badging, re.M,
    )
    ensure(len(badges) == 1, "Candidate aapt must report exactly one package/version line")
    badge_package, badge_code, badge_version = badges[0]
    ensure(badge_package == candidate["package"]
           and int(badge_code) == candidate["version_code"]
           and badge_version == candidate["version_name"],
           "Candidate aapt package/version disagrees with verified APK identity")
    labels = re.findall(r"^application-label:'([^']*)'\s*$", candidate_badging, re.M)
    ensure(labels == ["PhotoCraft"],
           "Candidate must have exactly one PhotoCraft app label")
    launchers = re.findall(r"^launchable-activity:\s+name='([^']+)'", candidate_badging, re.M)
    ensure(launchers == ["com.artcraft.photocraft.PhotoCraftActivity"],
           "Candidate must retain exactly one production PhotoCraft launcher")
    return {
        "status": "compatible_public_apk_identity",
        "reference_tag": PUBLIC_TAG,
        "reference_version_code": PUBLIC_VERSION_CODE,
        "candidate_tag": candidate_tag,
        "candidate_version_code": candidate["version_code"],
        "android_package": PUBLIC_PACKAGE,
        "certificate_sha256": PUBLIC_SIGNER_SHA256,
        "candidate_apk_sha256": candidate.get("apk_sha256"),
        "caveats": [
            "Identity verification is not owner approval to publish.",
            "Actual in-place update/data preservation must be tested on device.",
            "Possession/availability of the production signing key is not established.",
            "AI model weight rights, runtime lifecycle and rollback remain separate release gates.",
        ],
    }


def self_test() -> None:
    baseline = {
        "tag": PUBLIC_TAG, "package": PUBLIC_PACKAGE,
        "version_code": PUBLIC_VERSION_CODE,
        "version_name": "0.14.0-android.1",
        "signer_certificate_sha256": PUBLIC_SIGNER_SHA256,
    }
    new = {
        "tag": "photocraft-v0.14.0-android.2",
        "package": PUBLIC_PACKAGE, "version_code": PUBLIC_VERSION_CODE + 1,
        "version_name": "0.14.0-android.2",
        "signer_certificate_sha256": PUBLIC_SIGNER_SHA256,
        "apk_sha256": "a" * 64,
    }
    normal = (
        "package: name='com.artcraft.photocraft' versionCode='16790005' "
        "versionName='0.14.0-android.2'\n"
        "application-label:'PhotoCraft'\n"
        "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity' "
        "label='PhotoCraft'\n"
    )
    assert check_candidate(baseline, new, normal)["candidate_version_code"] == PUBLIC_VERSION_CODE + 1
    upgraded = {**new, "tag": "photocraft-v0.14.1-android.1", "version_name": "0.14.1-android.1"}
    upgraded_badging = normal.replace("0.14.0-android.2", "0.14.1-android.1")
    assert check_candidate(baseline, upgraded, upgraded_badging)["status"] == "compatible_public_apk_identity"
    rejected = [
        (baseline, {**new, "package": "com.artcraft.photocraft.ai.preview"}, normal),
        (baseline, {**new, "signer_certificate_sha256": "0" * 64}, normal),
        (baseline, {**new, "version_code": PUBLIC_VERSION_CODE}, normal),
        (baseline, {**new, "version_code": PUBLIC_VERSION_CODE - 1}, normal),
        (baseline, {**new, "tag": PUBLIC_TAG, "version_name": "0.14.0-android.1"}, normal),
        (baseline, {**new, "tag": "photocraft-v0.14.0-android.2", "version_name": "0.14.0-android.1"}, normal),
        ({**baseline, "signer_certificate_sha256": "0" * 64}, new, normal),
        ({**baseline, "version_code": 5}, new, normal),
        (baseline, new, normal.replace("application-label:'PhotoCraft'", "application-label:'PhotoCraft AI Preview'")),
        (baseline, new, normal.replace(
            "com.artcraft.photocraft.PhotoCraftActivity",
            "com.artcraft.photocraft.ai.preview.PhotoCraftActivity")),
        (baseline, {**new, "tag": "v0.14.0-android.2"}, normal),
        # Even with the right signer, refuse contradictory/ambiguous aapt data.
        (baseline, new, normal.replace("versionCode='16790005'", "versionCode='16790004'")),
        (baseline, new, normal.replace("versionName='0.14.0-android.2'", "versionName='0.14.0-android.3'")),
        (baseline, new, normal.replace("name='com.artcraft.photocraft'", "name='com.artcraft.photocraft.ai.preview'")),
        (baseline, new, normal + "application-label:'PhotoCraft'\n"),
        (baseline, new, normal + "launchable-activity: name='com.artcraft.photocraft.ai.preview.PhotoCraftActivity'\n"),
        (baseline, new, normal + "package: name='com.artcraft.photocraft' versionCode='16790005' versionName='0.14.0-android.2'\n"),
    ]
    for previous, future, badge in rejected:
        try:
            check_candidate(previous, future, badge)
        except ValueError:
            pass
        else:
            raise AssertionError("An incompatible PhotoCraft APK candidate was accepted")
    print(f"PASS: production upgrade compatibility gates ({len(rejected)} rejection scenarios)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true",
                        help="Offline tests only; no APKs, tools or network required")
    parser.add_argument("--reference-apk", type=Path)
    parser.add_argument("--candidate-apk", type=Path)
    parser.add_argument("--candidate-tag")
    parser.add_argument("--aapt", type=Path)
    parser.add_argument("--apksigner", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    ensure(all((args.reference_apk, args.candidate_apk, args.candidate_tag,
                args.aapt, args.apksigner, args.output)),
           "Provide both signed APKs, candidate tag, Android tools and output")
    ensure(args.reference_apk.resolve() != args.candidate_apk.resolve(),
           "Reference APK and candidate APK must be separate files")
    reference = inspect_apk(args.reference_apk, args.aapt, args.apksigner, PUBLIC_TAG)
    candidate = inspect_apk(args.candidate_apk, args.aapt, args.apksigner, args.candidate_tag)
    candidate_badging = subprocess.check_output(
        [str(args.aapt), "dump", "badging", str(args.candidate_apk)], text=True
    )
    report = check_candidate(reference, candidate, candidate_badging)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS: candidate matches published PhotoCraft signing/package identity")
    print("Candidate version:", report["candidate_tag"])
    print("No APK changed, signed, installed or released.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"STOP: PhotoCraft AI production candidate refused: {error}", file=sys.stderr)
        sys.exit(1)
