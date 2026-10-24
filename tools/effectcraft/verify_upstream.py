#!/usr/bin/env python3
"""Read-only EffectCraft upstream provenance guard. No build, push or signing."""
import json
from pathlib import Path
import urllib.request
from urllib.error import HTTPError

lock = json.loads((Path(__file__).resolve().parent / "upstream-lock.json").read_text())
tag = lock["official_tag"]
sha = lock["official_commit"]
assert tag == "v0.16.0" and sha == "9581b53c3f8945683252af0eb5fac79e0e43aed4"
assert lock["upstream_repository"] == "storytold/effectcraft"
assert lock["reference_builder_commit"] == "ac54d62d9d2d6f663295a4afd8972a7a3e79f9af"
assert lock["android_revision"] == 3
assert lock["android_version_name"] == "0.16.0-android.3"
assert lock["candidate_apk_name"] == "EffectCraft-v0.16.0-android.3-arm64-v8a.apk"
assert lock["expected_abi"] == "arm64-v8a"
assert lock["uploaded_icon_sha256"] == "6686489c6b64965610274461bcce0cc8ad2c27bf0bb5d7ef48ee4a303ea59389"
assert lock["version_code"] == 16781315 and lock["signing_certificate_sha256"] is None
assert lock["permanent_signing_ready"] is False and lock["public_release_enabled"] is False

def github(path):
    req = urllib.request.Request(
        "https://api.github.com/repos/storytold/effectcraft/" + path,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "KosmosSG-effectcraft-source-audit"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

release = github("releases/tags/" + tag)
assert release["draft"] is False and release["prerelease"] is False, "Not a stable published release"
assert release["tag_name"] == tag, "Release tag changed"
tag_ref = github("git/ref/tags/" + tag)
obj = tag_ref["object"]
if obj["type"] == "tag":
    obj = github("git/tags/" + obj["sha"])["object"]
assert obj["type"] == "commit" and obj["sha"] == sha, "Tag provenance changed"
print("PASS: Published stable EffectCraft release tag resolves to pinned commit", sha)
print("HOLD: This source audit does not verify APK contents, signing or device behavior.")
print("No build, temporary-key signing, release or schedule was run.")

