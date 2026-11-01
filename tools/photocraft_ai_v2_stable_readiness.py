#!/usr/bin/env python3
"""Read-only, fail-closed PhotoCraft AI V2 stable-release readiness checklist.

This check never signs, installs, merges, uploads, downloads or publishes.
A green audit means the checklist was evaluated, NOT that a stable build is approved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "docs" / "photocraft-ai-v2-stable-checklist.json"
EXPECTED_CERT = "EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936"
EXPECTED_PACKAGE = "com.artcraft.photocraft"
STEPS = (
    "v2_signed_ai_artifact_verified",
    "owner_feature_acceptance",
    "candidate_specific_owner_device_acceptance",
    "owner_signing_policy_compliance",
    "model_weight_and_dataset_rights_review",
    "real_device_sidecar_lifecycle_stress",
    "v2_to_v2_in_place_upgrade_and_data_retention",
    "original_signed_to_v2_migration_notice",
    "stable_release_owner_signoff",
)


def check_record(record: dict) -> tuple[bool, list[str]]:
    if type(record) is not dict:
        raise ValueError("Release checklist must be an object")
    if record.get("package") != EXPECTED_PACKAGE or record.get("v2_certificate_sha256") != EXPECTED_CERT:
        raise ValueError("V2 package/signing identity changed")
    if record.get("release_channel") != "prerelease" or record.get("pr_93_state") != "draft":
        raise ValueError("This pending checklist may not silently reclassify published releases or merge PR93")
    checks = record.get("checks")
    if type(checks) is not dict or set(checks) != set(STEPS):
        raise ValueError("Exact seven stable-release checks required")
    waiting = []
    for key in STEPS:
        entry = checks[key]
        if type(entry) is not dict or set(entry) != {"status", "evidence", "notes"}:
            raise ValueError("Malformed check: " + key)
        if entry["status"] not in ("passed", "pending", "failed"):
            raise ValueError("Unsupported check status: " + key)
        if type(entry["notes"]) is not str or not entry["notes"].strip():
            raise ValueError("Check needs explanatory notes: " + key)
        if type(entry["evidence"]) is not str:
            raise ValueError("Check evidence must be a string: " + key)
        if entry["status"] == "passed":
            u = urlparse(entry["evidence"])
            if u.scheme != "https" or u.hostname != "github.com" or not u.path.strip("/"):
                raise ValueError("Passing check needs GitHub review evidence: " + key)
        else:
            waiting.append(key)
    return (not waiting, waiting)


def self_test() -> None:
    from copy import deepcopy
    record = json.loads(RECORD.read_text())
    ready, blocked = check_record(record)
    assert not ready and "model_weight_and_dataset_rights_review" in blocked
    assert "real_device_sidecar_lifecycle_stress" in blocked
    assert "stable_release_owner_signoff" in blocked
    assert "candidate_specific_owner_device_acceptance" in blocked
    assert "owner_signing_policy_compliance" in blocked
    assert record["checks"]["owner_feature_acceptance"]["status"] == "passed"
    assert record["checks"]["candidate_specific_owner_device_acceptance"]["status"] == "pending"
    assert record["checks"]["owner_signing_policy_compliance"]["status"] == "pending"
    # The owner-tested android.2 preview and a green V2-signing job must not
    # silently approve android.3 or override the owner-only original-key policy.
    missing = deepcopy(record)
    del missing["checks"]["owner_signing_policy_compliance"]
    try:
        check_record(missing)
    except ValueError:
        pass
    else:
        raise AssertionError("Signing-policy gate can be omitted")
    for broken in ("", "0" * 64):
        x = deepcopy(record)
        x["v2_certificate_sha256"] = broken
        try:
            check_record(x)
        except ValueError:
            pass
        else:
            raise AssertionError("Incorrect signing identity was accepted")
    for key in STEPS:
        x = deepcopy(record)
        x["checks"][key]["status"] = "passed"
        x["checks"][key]["evidence"] = ""
        try:
            check_record(x)
        except ValueError:
            pass
        else:
            raise AssertionError("Check without reviewed evidence was accepted: " + key)
    x = deepcopy(record)
    x["release_channel"] = "stable"
    try:
        check_record(x)
    except ValueError:
        pass
    else:
        raise AssertionError("Unapproved stable promotion bypassed record guard")
    print("PASS: nine release gates validated and negative fail-closed cases rejected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--require-ready", action="store_true",
                        help="Fail when any stable release condition remains pending")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    record = json.loads(RECORD.read_text())
    ready, waiting = check_record(record)
    print("PhotoCraft AI V2 stable-release checklist")
    for name in STEPS:
        e = record["checks"][name]
        print(f"  {e['status'].upper():7} {name}: {e['notes']}")
    print("STABLE_READY=" + str(ready).lower())
    print("UNRESOLVED=" + ",".join(waiting))
    print("IMPORTANT: A green audit is not permission to publish or merge.")
    return 0 if ready or not args.require_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
