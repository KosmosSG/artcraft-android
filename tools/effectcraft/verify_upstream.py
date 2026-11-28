#!/usr/bin/env python3
"""Read-only EffectCraft upstream provenance guard. No build, push or signing."""
import json
from pathlib import Path
import urllib.request

lock = json.loads((Path(__file__).resolve().parent / "upstream-lock.json").read_text())
tag = lock["official_tag"]
sha = lock["official_commit"]
assert tag == "v0.25.1" and sha == "f5ce0dc56803a47ea9e483f400ab1c24426caa50"
assert lock["upstream_repository"] == "storytold/effectcraft"
assert lock["android_revision"] == 1
assert lock["android_version_name"] == "0.25.1-android.1"
assert lock["candidate_apk_name"] == "EffectCraft-v0.25.1-android.1-arm64-v8a.apk"
assert lock["expected_abi"] == "arm64-v8a"
assert lock["version_code"] == 16860001
assert lock["signing_certificate_sha256"] is None
assert lock["permanent_signing_ready"] is False
assert lock["public_release_enabled"] is False

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
print("PASS: published stable EffectCraft v0.25.1 resolves to pinned commit", sha)
print("PASS: ARM64 candidate metadata is 0.25.1-android.1 / 16860001")
print("HOLD: permanent signing and public release remain disabled.")
