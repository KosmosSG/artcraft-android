#!/usr/bin/env python3
"""Read-only candidate gate for future PhotoCraft AI V2 -> V2 upgrades.

A matching V2 signing certificate/versionCode means an Android installer can
attempt an upgrade, NOT that local files survive. Real owner device acceptance
and model licensing remain separate stable-release gates.
Never signs, merges, installs, downloads models or publishes releases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from photocraft_ai_candidate_compatibility import check_arm64_archive, release_key
from photocraft_ai_reference_signing import inspect as inspect_apk

PACKAGE = "com.artcraft.photocraft"
V2_CERT = "edda8ab30390e383e10450193b8ae5864312a6ff80e9d6c7f3437816524e6936"
V2_AI_PREVIEW_VERSION = "0.14.0-android.2"
V2_AI_PREVIEW_CODE = 16790005
# Hash of the actual unchanged APK in the public AI V2 preview release.
V2_AI_PREVIEW_SHA = "78d04d7e64ee9546e83dc98dfacc505dfbed5acf91e1f76e10e841ea76208598"
V2_AI_PREVIEW_IDENTITY_TAG = "photocraft-v0.14.0-android.2"
# The GitHub preview's actual tag includes '-ai-v2-preview'. inspect_apk's
# canonical tag argument validates embedded versionName only, while this
# fixed APK hash pins the exact published preview bytes independently.


def verify_pair(reference: dict, candidate: dict) -> dict:
    for label, item in (("baseline", reference), ("candidate", candidate)):
        if type(item) is not dict:
            raise ValueError(f"{label}: APK identity must be a mapping")
        if item.get("package") != PACKAGE:
            raise ValueError(f"{label}: incorrect Android package")
        if item.get("signer_certificate_sha256", "").lower() != V2_CERT:
            raise ValueError(f"{label}: not signed with permanent V2 certificate")
        if not isinstance(item.get("version_code"), int) or isinstance(item.get("version_code"), bool):
            raise ValueError(f"{label}: invalid versionCode type")
        if not isinstance(item.get("apk_sha256"), str) or len(item["apk_sha256"]) != 64:
            raise ValueError(f"{label}: invalid APK SHA-256")
    if (reference["version_name"], reference["version_code"],
            reference["apk_sha256"].lower()) != (
            V2_AI_PREVIEW_VERSION, V2_AI_PREVIEW_CODE, V2_AI_PREVIEW_SHA):
        raise ValueError("Baseline must match exact publicly published V2 AI preview APK")
    if candidate["apk_sha256"].lower() == reference["apk_sha256"].lower():
        raise ValueError("Candidate APK must be new bytes")
    if candidate["version_code"] <= V2_AI_PREVIEW_CODE:
        raise ValueError("Candidate Android versionCode must be higher than AI V2 preview")
    tag = candidate.get("tag")
    if not isinstance(tag, str) or not tag.startswith("photocraft-v"):
        raise ValueError("Candidate must use a canonical PhotoCraft release tag")
    if candidate.get("version_name") != tag.removeprefix("photocraft-v"):
        raise ValueError("Candidate tag must match Android versionName")
    release_key(tag)  # Verifies Android revision syntax and canonical naming.
    return {
        "package": PACKAGE,
        "signing_certificate_sha256": V2_CERT.upper(),
        "reference_version": V2_AI_PREVIEW_VERSION,
        "reference_version_code": V2_AI_PREVIEW_CODE,
        "reference_sha256": V2_AI_PREVIEW_SHA,
        "candidate_version": candidate["version_name"],
        "candidate_version_code": candidate["version_code"],
        "candidate_sha256": candidate["apk_sha256"],
        "apk_update_identity_check": "passed",
        "physical_device_in_place_update": "NOT TESTED",
        "data_preservation": "NOT TESTED",
        "model_rights": "NOT CLEARED",
        "stable_release_approval": "NOT GIVEN",
    }


def self_test() -> None:
    import copy
    ref = {
        "package": PACKAGE, "tag": V2_AI_PREVIEW_IDENTITY_TAG,
        "version_name": V2_AI_PREVIEW_VERSION, "version_code": V2_AI_PREVIEW_CODE,
        "apk_sha256": V2_AI_PREVIEW_SHA, "signer_certificate_sha256": V2_CERT,
    }
    target = {
        "package": PACKAGE, "tag": "photocraft-v0.14.0-android.3",
        "version_name": "0.14.0-android.3", "version_code": 16790006,
        "apk_sha256": "a" * 64, "signer_certificate_sha256": V2_CERT,
    }
    good = verify_pair(ref, target)
    assert good["apk_update_identity_check"] == "passed"
    assert good["data_preservation"] == "NOT TESTED"
    cases = [
        ("baseline", "apk_sha256", "b" * 64),
        ("baseline", "signer_certificate_sha256", "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"),
        ("baseline", "version_code", V2_AI_PREVIEW_CODE - 1),
        ("baseline", "version_name", "0.14.0-android.1"),
        ("candidate", "package", "com.artcraft.photocraft.ai.preview"),
        ("candidate", "signer_certificate_sha256", "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"),
        ("candidate", "version_code", V2_AI_PREVIEW_CODE),
        ("candidate", "version_code", V2_AI_PREVIEW_CODE - 1),
        ("candidate", "version_code", True),
        ("candidate", "tag", "photocraft-v0.14.0-android.2-ai-v2-preview"),
        ("candidate", "tag", "photocraft-v0.14.0-android.4"),
        ("candidate", "tag", "vectorcraft-v0.14.0-android.3"),
        ("candidate", "version_name", "0.14.1"),
        ("candidate", "apk_sha256", V2_AI_PREVIEW_SHA),
    ]
    for who, key, value in cases:
        r, c = copy.deepcopy(ref), copy.deepcopy(target)
        (r if who == "baseline" else c)[key] = value
        try:
            verify_pair(r, c)
        except ValueError:
            continue
        raise AssertionError(f"Fail-open regression: {who} {key} {value!r}")
    print(f"PASS: V2 baseline vs new stable-candidate identity gate; {len(cases)} negative regressions")
    print("NOT PROVEN: real-device data migration, licensing, or stable-release approval")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--reference-apk", type=Path)
    p.add_argument("--candidate-apk", type=Path)
    p.add_argument("--candidate-tag")
    p.add_argument("--aapt", type=Path)
    p.add_argument("--apksigner", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    if a.self_test:
        self_test()
        return 0
    if not all((a.reference_apk, a.candidate_apk, a.candidate_tag,
                a.aapt, a.apksigner, a.output)):
        p.error("Read-only comparison requires both signed APKs, candidate tag and Android tools")
    if a.reference_apk.resolve() == a.candidate_apk.resolve():
        raise ValueError("Reference and candidate must be different APKs")
    ref = inspect_apk(a.reference_apk, a.aapt, a.apksigner, V2_AI_PREVIEW_IDENTITY_TAG)
    candidate = inspect_apk(a.candidate_apk, a.aapt, a.apksigner, a.candidate_tag)
    report = verify_pair(ref, candidate)
    # Verify the actual candidate archive includes arm64 binaries and no
    # bundled model weights, keystores, unsafe paths or unexpected ABI.
    report["archive"] = check_arm64_archive(a.candidate_apk)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS: Signed V2 candidate is identity/version/ABI-compatible with AI V2 preview")
    print("NOT PROVEN: on-device upgrade, data preservation, model rights or stable release approval")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("STOP: PhotoCraft AI V2 candidate refused: " + str(error), file=sys.stderr)
        sys.exit(1)
