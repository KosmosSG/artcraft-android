"""EffectCraft-only preliminary release filtering, NOT an APK signature verifier.

This is a safe reference for the eventual Android in-app updater. A GitHub
release record can establish the application-specific tag and asset name, but
CANNOT establish APK authenticity or that a signing certificate matches.
Do not offer an install action until signature + certificate + hash are verified.
"""

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

APP = "effectcraft"
TAG_RE = re.compile(r"^effectcraft-v([0-9]+)\.([0-9]+)\.([0-9]+)-android\.([1-9][0-9]*)$")
VERSION_RE = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)-android\.([1-9][0-9]*)$")
RELEASE_PREFIX = "https://github.com/KosmosSG/artcraft-android/releases/download/"


@dataclass(frozen=True)
class Candidate:
    version_name: str
    release_tag: str
    asset_url: str
    # This deliberately does not claim a verified APK, certificate, or device compatibility.
    verification_required: bool = True


def parse_version(version_name: str) -> tuple[int, int, int, int] | None:
    if not isinstance(version_name, str):
        return None
    match = VERSION_RE.fullmatch(version_name)
    return tuple(map(int, match.groups())) if match else None


def parse_tag(tag: str) -> tuple[int, int, int, int] | None:
    if not isinstance(tag, str):
        return None
    match = TAG_RE.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None


def preliminary_candidates(
    releases: Sequence[Mapping], installed_version_name: str
) -> list[Candidate]:
    """Filter metadata without trusting it as a signed update.

    Excludes upstream desktop tags, other apps, draft/prerelease records,
    duplicate or missing exact APK filenames and untrusted download hosts.
    No release metadata can bypass APK hash and certificate verification.
    """
    current = parse_version(installed_version_name)
    if current is None:
        return []  # Wrong/unknown installed version; fail closed.
    result: list[Candidate] = []
    seen: set[str] = set()
    for release in releases:
        if not isinstance(release, Mapping):
            continue
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name", "")
        value = parse_tag(tag)
        if value is None or value <= current or tag in seen:
            continue
        version = f"{value[0]}.{value[1]}.{value[2]}-android.{value[3]}"
        target_name = f"EffectCraft-{version}-arm64-v8a.apk"
        expected_prefix = f"{RELEASE_PREFIX}{tag}/"
        assets = release.get("assets") or []
        matching = [
            asset for asset in assets
            if isinstance(asset, Mapping)
            and asset.get("name") == target_name
            and asset.get("browser_download_url") == expected_prefix + target_name
        ]
        if len(matching) != 1:
            continue
        result.append(Candidate(version, tag, matching[0]["browser_download_url"]))
        seen.add(tag)
    return sorted(result, key=lambda c: parse_version(c.version_name), reverse=True)
