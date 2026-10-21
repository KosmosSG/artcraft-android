#!/usr/bin/env python3
"""Read-only official stable-release detection for EffectCraft. Never builds or publishes."""
import json
from pathlib import Path
import re
import urllib.request

LOCK = json.loads((Path(__file__).resolve().parent / "upstream-lock.json").read_text())
API = "https://api.github.com/repos/storytold/effectcraft/"

def get(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "KosmosSG-effectcraft-upstream-detection"
    })
    with urllib.request.urlopen(request, timeout=25) as resp:
        return json.load(resp)

candidates = [
    release for release in get(API + "releases?per_page=100")
    if not release.get("draft") and not release.get("prerelease")
    and re.fullmatch(r"v\\d+\\.\\d+\\.\\d+", release.get("tag_name", ""))
]
if not candidates:
    raise SystemExit("No official stable semver release found (fail closed).")
latest = max(candidates, key=lambda release: tuple(map(int, release["tag_name"][1:].split("."))))
ref = get(API + "git/ref/tags/" + latest["tag_name"])
obj = ref["object"]
if obj["type"] == "tag":
    obj = get(API + "git/tags/" + obj["sha"])["object"]
if obj["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", obj["sha"]):
    raise SystemExit("Stable tag did not resolve to an immutable commit.")
summary = {
    "official_repo": LOCK["upstream_repository"],
    "latest_stable_tag": latest["tag_name"],
    "latest_stable_commit": obj["sha"],
    "approved_tag": LOCK["official_tag"],
    "approved_commit": LOCK["official_commit"],
    "review_required": (
        latest["tag_name"] != LOCK["official_tag"]
        or obj["sha"] != LOCK["official_commit"]
    ),
    "decision": "source review only; never auto-merge, rebuild, sign or publish",
}
print(json.dumps(summary, indent=2))
