#!/usr/bin/env python3
"""Read-only PDFCraft official stable release detector.

Never checks out a moving main branch, creates Git refs, builds APKs, signs or publishes
anything. Detection is *not* an update. A version change requires a separate source/API/
licence/payload review and a fresh guarded candidate PR.

No tokens or environment secrets are read; public GitHub API endpoints only.
"""
from __future__ import annotations

import json
import re
import sys
from urllib.request import Request, urlopen

REPOSITORY = "storytold/pdfcraft"
BASELINE_TAG = "v0.10.1"
BASELINE_SHA = "b77d57000c22c760f731206f6cf14486d149de72"
BASE = f"https://api.github.com/repos/{REPOSITORY}"


def github_json(endpoint: str) -> dict:
    if not endpoint.startswith(BASE + "/"):
        raise ValueError("Refusing URL outside PDFCraft's official repository")
    request = Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "KosmosSG-PDFCraft-android-audit",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def resolve_tag(tag: str) -> str:
    ref = github_json(f"{BASE}/git/ref/tags/{tag}")
    obj = ref["object"]
    for _ in range(3):
        if obj["type"] == "commit":
            sha = obj["sha"]
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise ValueError("Invalid commit digest returned by GitHub")
            return sha
        if obj["type"] != "tag":
            raise ValueError("Unexpected object type in upstream release tag")
        obj = github_json(f"{BASE}/git/tags/{obj['sha']}")["object"]
    raise ValueError("Annotated tag chain too deep")


def main() -> int:
    try:
        # GitHub's /releases/latest excludes drafts/prereleases; check explicitly, too.
        release = github_json(f"{BASE}/releases/latest")
        tag = release["tag_name"]
        if release.get("draft") or release.get("prerelease"):
            raise ValueError("Only stable public releases are acceptable")
        if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
            raise ValueError("Unexpected upstream tag format: manual review required")
        sha = resolve_tag(tag)
        pinned = resolve_tag(BASELINE_TAG)
        if pinned != BASELINE_SHA:
            raise ValueError("Pinned baseline release tag no longer resolves to audited commit")
        changed = tag != BASELINE_TAG or sha != BASELINE_SHA
        result = {
            "repository": REPOSITORY,
            "stable_tag": tag,
            "stable_commit": sha,
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_SHA,
            "review_required": changed,
            "next_action": "Review source/API/licences; do not build/sign/publish automatically" if changed else "No upstream change since the pinned candidate",
            "android_release_created": False,
            "android_apk_built": False,
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        # Fail closed: network or provenance errors must not become false no-change reports.
        print(f"PDFCraft stable release audit failed closed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
