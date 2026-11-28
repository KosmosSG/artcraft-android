#!/usr/bin/env python3
"""Offline EffectCraft upstream lock consistency guard.

The CI workflow independently checks out the official tag by immutable commit SHA
and validates the Cargo manifest. Avoid unauthenticated GitHub API calls here:
GitHub Actions runners can hit shared unauthenticated API rate limits.
"""
import json
from pathlib import Path

lock = json.loads((Path(__file__).resolve().parent / "upstream-lock.json").read_text())
expected = {
    "app": "effectcraft",
    "upstream_repository": "storytold/effectcraft",
    "official_tag": "v0.25.1",
    "official_commit": "f5ce0dc56803a47ea9e483f400ab1c24426caa50",
    "official_release_url": "https://github.com/storytold/effectcraft/releases/tag/v0.25.1",
    "android_revision": 1,
    "android_version_name": "0.25.1-android.1",
    "candidate_apk_name": "EffectCraft-v0.25.1-android.1-arm64-v8a.apk",
    "expected_abi": "arm64-v8a",
    "proposed_package": "com.artcraft.effectcraft",
    "version_code": 16860001,
    "signing_certificate_sha256": None,
    "permanent_signing_ready": False,
    "public_release_enabled": False,
    "uploaded_icon_sha256": "7b964522df335124bffa56213819951187c7fdb2e4fce3a337176cfab88c33ef",
    "icon_in_apk_verified": False,
}
for key, value in expected.items():
    assert lock.get(key) == value, (key, lock.get(key), value)
print("PASS: immutable EffectCraft v0.25.1 lock and 0.25.1-android.1 test metadata")
print("HOLD: permanent signing and public release remain disabled.")
