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
import re
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
# 1 Nov 2026: the public owner-tested core PhotoCraft editor became stable
# at android.4, permanently signed with the SAME V2 certificate. Its AI
# subsystem remains experimental. This exact stable APK is now the *minimum*
# future update baseline, even if comparing a historical android.2 preview.
V2_STABLE_VERSION = "0.14.0-android.4"
V2_STABLE_CODE = 16790007
V2_STABLE_SHA = "d50857fe7d563821563d29842299858bbda09ea49e3786c420ec02f21b8e6367"
V2_STABLE_TAG = "photocraft-v0.14.0-android.4"
PUBLISHED_BASELINES = {
    V2_AI_PREVIEW_VERSION: (V2_AI_PREVIEW_CODE, V2_AI_PREVIEW_SHA),
    V2_STABLE_VERSION: (V2_STABLE_CODE, V2_STABLE_SHA),
}
# The older preview's actual GitHub tag contains '-ai-v2-preview'. We pin
# the hash of the exact APK rather than treating the tag as a versionName.



def verify_production_launcher_badging(badging: str) -> None:
    """Require the actual signed APK to retain PhotoCraft's public UI identity.

    This is intentionally checked against aapt output, not source declarations:
    a same-package, same-certificate APK could otherwise pass V2 update
    identity tests while silently replacing the app label or launch activity.
    """
    if not isinstance(badging, str):
        raise ValueError("Candidate aapt badging must be text")
    lines = badging.splitlines()
    labels = [line for line in lines if line.startswith("application-label:")]
    if labels != ["application-label:'PhotoCraft'"]:
        raise ValueError("Candidate must retain exactly one PhotoCraft app label")
    launchers = [line for line in lines if line.startswith("launchable-activity:")]
    if len(launchers) != 1:
        raise ValueError("Candidate must have exactly one production launcher")
    match = re.fullmatch(
        r"launchable-activity:\s+name='([^']+)'(?:\s+.*)?", launchers[0]
    )
    if match is None or match.group(1) != "com.artcraft.photocraft.PhotoCraftActivity":
        raise ValueError("Candidate must retain the PhotoCraft launcher activity")


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
        if not isinstance(item.get("apk_sha256"), str) or re.fullmatch(r"[0-9a-fA-F]{64}", item["apk_sha256"]) is None:
            raise ValueError(f"{label}: invalid APK SHA-256")
    baseline = PUBLISHED_BASELINES.get(reference["version_name"])
    if baseline is None or (reference["version_code"],
                            reference["apk_sha256"].lower()) != baseline:
        raise ValueError("Reference APK must match an exact published V2 PhotoCraft release")
    if candidate["apk_sha256"].lower() in {sha for _, sha in PUBLISHED_BASELINES.values()}:
        raise ValueError("Candidate APK must differ from all pinned published V2 releases")
    if candidate["version_code"] <= V2_STABLE_CODE:
        raise ValueError("Candidate versionCode must exceed current stable PhotoCraft android.4")
    tag = candidate.get("tag")
    if not isinstance(tag, str) or not tag.startswith("photocraft-v"):
        raise ValueError("Candidate must use a canonical PhotoCraft release tag")
    if candidate.get("version_name") != tag.removeprefix("photocraft-v"):
        raise ValueError("Candidate tag must match Android versionName")
    if release_key(tag) <= release_key(V2_STABLE_TAG):
        raise ValueError("Candidate versionName must be newer than current stable PhotoCraft android.4")
    return {
        "package": PACKAGE,
        "signing_certificate_sha256": V2_CERT.upper(),
        "reference_version": reference["version_name"],
        "reference_version_code": reference["version_code"],
        "reference_sha256": reference["apk_sha256"],
        "minimum_published_stable_version": V2_STABLE_VERSION,
        "minimum_published_stable_version_code": V2_STABLE_CODE,
        "candidate_version": candidate["version_name"],
        "candidate_version_code": candidate["version_code"],
        "candidate_sha256": candidate["apk_sha256"],
        "apk_update_identity_check": "passed",
        "physical_device_in_place_update": "NOT TESTED",
        "data_preservation": "NOT TESTED",
        "model_rights": "NOT CLEARED",
        "future_ai_update_approval": "NOT GIVEN",
        "existing_editor_stable_release": V2_STABLE_TAG,
    }


def self_test() -> None:
    import copy
    good_badging = (
        "package: name='com.artcraft.photocraft' versionCode='16790008' "
        "versionName='0.14.0-android.5'\n"
        "application-label:'PhotoCraft'\n"
        "application-label-en:'PhotoCraft'\n"
        "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity' "
        "label='PhotoCraft' icon='res/drawable/icon.png'\n"
    )
    verify_production_launcher_badging(good_badging)
    for bad in (
        good_badging.replace("application-label:'PhotoCraft'", "application-label:'PhotoCraft AI'"),
        good_badging.replace("application-label:'PhotoCraft'\n", ""),
        good_badging + "application-label:'PhotoCraft'\n",
        good_badging + "application-label:garbled\n",
        good_badging.replace("PhotoCraftActivity", "PreviewActivity"),
        good_badging.replace("launchable-activity:", "other-activity:"),
        good_badging + "launchable-activity: name='com.artcraft.photocraft.PhotoCraftActivity'\n",
        good_badging + "launchable-activity:broken\n",
    ):
        try:
            verify_production_launcher_badging(bad)
        except ValueError:
            continue
        raise AssertionError("Fail-open regression: unsafe candidate launcher/label")
    ref = {
        "package": PACKAGE, "tag": V2_AI_PREVIEW_IDENTITY_TAG,
        "version_name": V2_AI_PREVIEW_VERSION, "version_code": V2_AI_PREVIEW_CODE,
        "apk_sha256": V2_AI_PREVIEW_SHA, "signer_certificate_sha256": V2_CERT,
    }
    target = {
        "package": PACKAGE, "tag": "photocraft-v0.14.0-android.5",
        "version_name": "0.14.0-android.5", "version_code": 16790008,
        "apk_sha256": "a" * 64, "signer_certificate_sha256": V2_CERT,
    }
    good = verify_pair(ref, target)
    assert good["apk_update_identity_check"] == "passed"
    assert good["data_preservation"] == "NOT TESTED"
    assert good["minimum_published_stable_version_code"] == 16790007
    stable_ref = {
        **ref, "tag": V2_STABLE_TAG, "version_name": V2_STABLE_VERSION,
        "version_code": V2_STABLE_CODE, "apk_sha256": V2_STABLE_SHA,
    }
    assert verify_pair(stable_ref, target)["reference_version"] == V2_STABLE_VERSION
    # A historical .2 preview may still be a reference, but no downgrade
    # below today's public stable .4 is ever permitted.
    stale_candidate = {
        **target, "tag": V2_STABLE_TAG, "version_name": V2_STABLE_VERSION,
        "version_code": V2_STABLE_CODE,
    }
    for prev in (ref, stable_ref):
        try:
            verify_pair(prev, stale_candidate)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted a candidate that cannot upgrade stable android.4")
    cases = [
        ("baseline", "apk_sha256", "b" * 64),
        ("baseline", "signer_certificate_sha256", "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"),
        ("baseline", "version_code", V2_AI_PREVIEW_CODE - 1),
        ("baseline", "version_name", "0.14.0-android.1"),
        ("candidate", "package", "com.artcraft.photocraft.ai.preview"),
        ("candidate", "signer_certificate_sha256", "45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef"),
        ("candidate", "version_code", V2_STABLE_CODE),
        ("candidate", "version_code", V2_STABLE_CODE - 1),
        ("candidate", "version_code", True),
        ("candidate", "tag", "photocraft-v0.14.0-android.2-ai-v2-preview"),
        ("candidate", "tag", "photocraft-v0.14.0-android.4"),
        ("candidate", "tag", "vectorcraft-v0.14.0-android.3"),
        # A higher numeric versionCode must not conceal a versionName rollback.
        ("candidate", "tag", "photocraft-v0.14.0-android.3"),
        ("candidate", "tag", "photocraft-v0.13.0-android.3"),
        ("candidate", "tag", "photocraft-v0.14.0-android.1"),
        ("candidate", "apk_sha256", "g" * 64),
        ("baseline", "apk_sha256", "z" * 64),
        ("candidate", "version_name", "0.14.1"),
        ("candidate", "apk_sha256", V2_AI_PREVIEW_SHA),
    ]
    for who, key, value in cases:
        r, c = copy.deepcopy(ref), copy.deepcopy(target)
        (r if who == "baseline" else c)[key] = value
        if who == "candidate" and key == "tag" and value in (
            "photocraft-v0.14.0-android.3", "photocraft-v0.13.0-android.3",
            "photocraft-v0.14.0-android.1"
        ):
            c["version_name"] = value.removeprefix("photocraft-v")
        try:
            verify_pair(r, c)
        except ValueError:
            continue
        raise AssertionError(f"Fail-open regression: {who} {key} {value!r}")
    print(f"PASS: V2 current-stable (.4) plus historical-preview (.2) baseline gate; {len(cases)} negative regressions")
    print("NOT PROVEN: real-device data migration, licensing, or stable-release approval")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--reference-apk", type=Path)
    p.add_argument("--reference-version", choices=tuple(PUBLISHED_BASELINES),
                   default=V2_STABLE_VERSION,
                   help="Expected signed baseline APK version; defaults to current stable android.4")
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
    ref = inspect_apk(a.reference_apk, a.aapt, a.apksigner, "photocraft-v" + a.reference_version)
    candidate = inspect_apk(a.candidate_apk, a.aapt, a.apksigner, a.candidate_tag)
    candidate_badging = subprocess.check_output(
        [str(a.aapt), "dump", "badging", str(a.candidate_apk)], text=True
    )
    verify_production_launcher_badging(candidate_badging)
    report = verify_pair(ref, candidate)
    report["production_label_launcher_check"] = "passed"
    # Verify the actual candidate archive includes arm64 binaries and no
    # bundled model weights, keystores, unsafe paths or unexpected ABI.
    report["archive"] = check_arm64_archive(a.candidate_apk)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS: V2 candidate signed identity/version/ABI exceeds current published stable android.4")
    print("NOT PROVEN: on-device upgrade, data preservation, model rights or future release approval")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("STOP: PhotoCraft AI V2 candidate refused: " + str(error), file=sys.stderr)
        sys.exit(1)
