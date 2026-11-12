#!/usr/bin/env python3
"""Read-only FilmCraft release audit. Never checks out source, changes tags, or publishes."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

LOCK = Path(__file__).with_name("source-lock.json")
API = "https://api.github.com/repos/storytold/filmcraft/"


def get_json(path):
    request = urllib.request.Request(
        API + path,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "FilmCraft-Android-Source-Guard"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def resolve_tag(tag):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Only numeric official stable release tags are allowed")
    ref = get_json("git/ref/tags/" + tag)
    obj = ref["object"]
    if obj["type"] == "tag":
        obj = get_json("git/tags/" + obj["sha"])["object"]
    if obj["type"] != "commit" or not re.fullmatch(r"[0-9a-f]{40}", obj["sha"]):
        raise ValueError("Release tag did not resolve to exactly one commit")
    return obj["sha"]


def audit(online):
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    o, c, r = lock["official"], lock["candidate"], lock["reviewed_android_reference"]
    assert o["repo"] == "storytold/filmcraft"
    assert re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", o["release_tag"])
    assert o["version"] == o["release_tag"][1:]
    assert re.fullmatch(r"[0-9a-f]{40}", o["commit"])
    assert r == {"repo": "MostafaXS1/artcraft-android",
                 "commit": "ac54d62d9d2d6f663295a4afd8972a7a3e79f9af"}
    assert c["package_name"] == "com.artcraft.filmcraft"
    assert c["abi"] == "arm64-v8a"
    assert c["version_name"] == o["version"] + "-android.1"
    assert c["requested_apk_name"] == "filmcraft-" + c["version_name"] + ".apk"
    assert c["version_code"] is None, "VersionCode must not be guessed or silently reserved"
    assert not c["apk_built"] and not c["tablet_tested"]
    result = {"pin_valid": True, "tag": o["release_tag"],
              "locked_commit": o["commit"], "check_mode": "online" if online else "offline",
              "safe_to_publish": False}
    if online:
        actual = resolve_tag(o["release_tag"])
        result["observed_locked_tag_commit"] = actual
        if actual != o["commit"]:
            raise ValueError("Existing release tag moved; STOP and inspect provenance")
        newest = get_json("releases/latest")
        newest_tag = newest["tag_name"]
        if newest.get("draft") or newest.get("prerelease"):
            raise ValueError("Unexpected unstable /latest response")
        result["latest_stable_tag"] = newest_tag
        result["latest_stable_commit"] = resolve_tag(newest_tag)
        result["upstream_review_needed"] = (
            newest_tag != o["release_tag"] or result["latest_stable_commit"] != actual
        )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true",
                        help="Check official GitHub release and tag integrity; read-only")
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.online), sort_keys=True, indent=2))
    except (AssertionError, ValueError, KeyError, OSError,
            urllib.error.HTTPError, urllib.error.URLError) as exc:
        print("FilmCraft source audit BLOCKED: " + str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
