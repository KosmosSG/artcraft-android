#!/usr/bin/env python3
"""One shared, fail-closed naming contract for future ArtCraft Android releases.

This tool never signs, publishes, alters upstream sources, or derives an Android
versionCode. The latter MUST be strictly greater than every installed/released
versionCode and the permanent signing certificate MUST remain unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = re.compile(r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-android\.([1-9][0-9]*)$")
VERSIONING_SCHEME = "upstream-semver-plus-android-revision-v1"


def apps() -> dict:
    config = json.loads((ROOT / "configs/release-gates/suite.json").read_text())
    if config["version_naming"]["scheme"] != VERSIONING_SCHEME:
        raise ValueError("Unrecognized suite Android versioning policy")
    return config["apps"]


def release_identity(app: str, upstream: str, revision: int) -> dict:
    all_apps = apps()
    if app not in all_apps:
        raise ValueError("Unknown ArtCraft app: " + app)
    m = UPSTREAM.fullmatch(upstream)
    if not m:
        raise ValueError("Requires an official stable upstream vMAJOR.MINOR.PATCH")
    if type(revision) is not int or revision < 1:
        raise ValueError("Android revision must be a positive integer")
    version_name = ".".join(m.groups()) + f"-android.{revision}"
    display_name = all_apps[app]["display_name"]
    if "/" in display_name:
        # GridCraft / ExcelCraft is unresolved: do not invent its public branding.
        raise ValueError("Resolve public app display name before publishing: " + app)
    return {
        "app": app,
        "versionName": version_name,
        "tag": f"{app}-v{version_name}",
        "title": f"{display_name} v{version_name}",
        "apk": f"{display_name}-v{version_name}-arm64-v8a.apk",
    }


def verify_release(app: str, upstream: str, revision: int, *,
                   version_name: str, tag: str, apk: str,
                   title: str | None = None,
                   previous_code: int | None = None,
                   new_code: int | None = None) -> dict:
    expected = release_identity(app, upstream, revision)
    assert VERSION.fullmatch(expected["versionName"])
    actual = {"versionName": version_name, "tag": tag, "apk": apk}
    if title is not None:
        actual["title"] = title
    for key, value in actual.items():
        if value != expected[key]:
            raise ValueError(f"{key} mismatch: got {value!r}; expected {expected[key]!r}")
    if (previous_code is None) != (new_code is None):
        raise ValueError("Provide both old and new versionCode or neither")
    if previous_code is not None:
        if type(previous_code) is not int or type(new_code) is not int or new_code <= previous_code:
            raise ValueError("APK update requires strictly increasing Android versionCode")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "verify"))
    parser.add_argument("--app", required=True)
    parser.add_argument("--upstream", required=True, help="Pinned official stable vX.Y.Z")
    parser.add_argument("--revision", required=True, type=int)
    parser.add_argument("--version-name")
    parser.add_argument("--tag")
    parser.add_argument("--apk")
    parser.add_argument("--title")
    parser.add_argument("--previous-code", type=int)
    parser.add_argument("--new-code", type=int)
    args = parser.parse_args()
    if args.command == "plan":
        result = release_identity(args.app, args.upstream, args.revision)
    else:
        if not args.version_name or not args.tag or not args.apk:
            parser.error("verify requires --version-name, --tag and --apk")
        result = verify_release(args.app, args.upstream, args.revision,
                                version_name=args.version_name, tag=args.tag,
                                apk=args.apk, title=args.title,
                                previous_code=args.previous_code,
                                new_code=args.new_code)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
