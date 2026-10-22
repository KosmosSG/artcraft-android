#!/usr/bin/env python3
"""Read-only EffectCraft upstream provenance guard. No build, push or signing."""
import json
from pathlib import Path
import urllib.request
from urllib.error import HTTPError

lock = json.loads((Path(__file__).resolve().parent / "upstream-lock.json").read_text())
tag = lock["official_tag"]
sha = lock["official_commit"]
assert tag == "v0.14.0" and sha == "26b40199b72121aa7f4e55a63718e1b4dd48a859"
assert lock["upstream_repository"] == "storytold/effectcraft"
assert lock["reference_builder_commit"] == "ac54d62d9d2d6f663295a4afd8972a7a3e79f9af"
assert lock["android_revision"] == 1
assert lock["android_version_name"] == "0.14.0-android.1"
assert lock["candidate_apk_name"] == "EffectCraft-0.14.0-android.1-arm64-v8a.apk"
assert lock["expected_abi"] == "arm64-v8a"
assert lock["uploaded_icon_sha256"] == "376a9b60f3ca15174a8a4e07563d5f4402a03011bc86e56395134f3f8f88661b"
assert lock["version_code"] is None and lock["signing_certificate_sha256"] is None
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
print("HOLD: VersionCode, prior identity, approved Ec APK integration and permanent signing unverified.")
print("No build, temporary-key signing, release or schedule was run.")
