#!/usr/bin/env python3
"""Report-only comparison of official Storytold releases, main, and published Android releases.

No git writes, workflow dispatch, APK builds, signing, releases, issue/PR creation,
or repository mutations. GitHub API GET requests only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

APPS = (
    "photocraft", "vectorcraft", "designcraft", "effectcraft", "lightcraft",
    "pdfcraft", "wordcraft", "gridcraft", "filmcraft", "deckcraft",
)
ANDROID_REPO = "KosmosSG/artcraft-android"
API_ROOT = "https://api.github.com"
REPORT_DIR = Path("reports")
PREVIEW_MARKER = re.compile(r"(?<![A-Za-z0-9])(?:pre[- ]?release|preview|candidate|testing|test|rc\d*)(?![A-Za-z])", re.I)


class ApiFailure(RuntimeError):
    pass


def api_get(path: str):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "artcraft-upstream-compare-readonly",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(API_ROOT + path, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        reason = exc.reason or ""
        raise ApiFailure(f"GitHub API HTTP {exc.code} ({reason}) for {path}") from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise ApiFailure(f"GitHub API request failed for {path}: {exc}") from exc


def release_pages(repo: str, limit: int = 8):
    releases = []
    for page in range(1, limit + 1):
        batch = api_get(f"/repos/{repo}/releases?per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ApiFailure(f"Unexpected releases response for {repo}")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
    raise ApiFailure(f"More than {limit * 100} releases for {repo}; refusing partial baseline")


def published(release):
    return not release.get("draft") and bool(release.get("published_at"))


def android_version(release, app):
    tag = str(release.get("tag_name") or "")
    match = re.fullmatch(rf"{re.escape(app)}-v(\d+\.\d+\.\d+)-android\.(\d+)(?:[-.][\w.-]+)?", tag, re.I)
    return match.group(1) if match else None


def preview(release):
    if release.get("prerelease"):
        return True
    name = str(release.get("name") or "")
    tag = str(release.get("tag_name") or "")
    # GitHub's prerelease field can be false for a release titled "Prerelease".
    return bool(PREVIEW_MARKER.search(name) or PREVIEW_MARKER.search(tag))


def apk_assets(release):
    return [
        {"name": x.get("name"), "size_bytes": x.get("size"),
         "url": x.get("browser_download_url"), "digest": x.get("digest")}
        for x in (release.get("assets") or [])
        if str(x.get("name") or "").lower().endswith(".apk")
    ]


def release_info(release, app=None):
    if release is None:
        return None
    return {
        "tag": release.get("tag_name"),
        "title": release.get("name"),
        "published_at": release.get("published_at"),
        "url": release.get("html_url"),
        "is_prerelease": preview(release),
        "github_prerelease": bool(release.get("prerelease")),
        "upstream_version": android_version(release, app) if app else None,
        "apk_assets": apk_assets(release),
    }


def latest_android(releases, app):
    matching = [r for r in releases if published(r) and android_version(r, app)]
    matching.sort(key=lambda r: (r.get("published_at") or "", r.get("created_at") or ""), reverse=True)
    latest = matching[0] if matching else None
    # Preserve the latest published non-preview release with an APK as the
    # protected Android baseline. Never silently promote a test prerelease.
    stable = next((r for r in matching if not preview(r) and apk_assets(r)), None)
    return latest, stable


def latest_official(repo):
    try:
        stable = api_get(f"/repos/{repo}/releases/latest")
        if stable.get("draft") or stable.get("prerelease") or not stable.get("tag_name"):
            raise ApiFailure(f"Official latest release isn't stable: {repo}")
        return stable
    except ApiFailure as exc:
        if "HTTP 404" not in str(exc):
            raise
        candidates = [r for r in release_pages(repo) if published(r) and not r.get("prerelease")]
        if not candidates:
            raise ApiFailure(f"No official stable release found for {repo}") from exc
        candidates.sort(key=lambda r: r.get("published_at") or "", reverse=True)
        return candidates[0]


def version_tuple(text):
    if not text:
        return None
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text))
    return tuple(map(int, match.groups())) if match else None


def gap_status(upstream, latest, baseline):
    upstream_v = version_tuple(str(upstream.get("tag_name") or ""))
    if upstream_v is None:
        return "REVIEW: upstream version cannot be parsed"
    if not latest:
        return "REVIEW: no published Android release found"
    m = re.search(r"-v(\d+\.\d+\.\d+)-android\.", str(latest.get("tag_name") or ""), re.I)
    latest_v = version_tuple(m.group(1)) if m else None
    stable_v = None
    if baseline:
        m = re.search(r"-v(\d+\.\d+\.\d+)-android\.", str(baseline.get("tag_name") or ""), re.I)
        stable_v = version_tuple(m.group(1)) if m else None
    if latest_v is None:
        return "REVIEW: Android version cannot be parsed"
    if latest_v < upstream_v:
        return "NEW STABLE UPSTREAM: Android published release is behind"
    if latest_v > upstream_v:
        return "REVIEW: Android references a newer or different upstream version"
    if stable_v is None:
        return "PREVIEW MATCH ONLY: no verified stable Android APK baseline"
    if stable_v < upstream_v:
        return "PREVIEW MATCH ONLY: protected stable Android baseline is behind"
    return "MATCH: published stable Android APK uses current upstream version"


def recent_commits(app):
    rows = api_get(f"/repos/storytold/{app}/commits?sha=main&per_page=5")
    return [
        {
            "sha": x.get("sha"),
            "message": str(((x.get("commit") or {}).get("message") or "").splitlines()[0])[:180],
            "date": ((x.get("commit") or {}).get("committer") or {}).get("date"),
            "url": x.get("html_url"),
        }
        for x in rows[:5]
    ]


def inspect_app(app, android_releases):
    upstream_repo = f"storytold/{app}"
    stable_upstream = latest_official(upstream_repo)
    latest, baseline = latest_android(android_releases, app)
    branch = api_get(f"/repos/{upstream_repo}/branches/main")
    main_sha = ((branch.get("commit") or {}).get("sha"))
    if not main_sha:
        raise ApiFailure(f"No main commit SHA for {upstream_repo}")
    tag = quote(str(stable_upstream["tag_name"]), safe="")
    comparison = api_get(f"/repos/{upstream_repo}/compare/{tag}...main?per_page=1")
    compare_result = {
        "status": comparison.get("status"),
        "ahead_by": comparison.get("ahead_by"),
        "behind_by": comparison.get("behind_by"),
        "total_commits": comparison.get("total_commits"),
        "url": comparison.get("html_url") or f"https://github.com/{upstream_repo}/compare/{tag}...main",
    }
    return {
        "app": app,
        "official_stable_upstream": release_info(stable_upstream),
        "latest_published_android": release_info(latest, app),
        "protected_stable_android_baseline": release_info(baseline, app),
        "release_gap": gap_status(stable_upstream, latest, baseline),
        "upstream_main": {
            "sha": main_sha,
            "url": f"https://github.com/{upstream_repo}/commit/{main_sha}",
            "comparison_to_stable": compare_result,
            "recent_commits": recent_commits(app),
        },
        "warnings": (
            (["Latest Android release is marked as a prerelease/preview."] if latest and preview(latest) else [])
            + (["Latest published Android release has no APK asset."] if latest and not apk_assets(latest) else [])
            + (["Protected stable Android baseline is missing."] if baseline is None else [])
            + (["Upstream tag and main have diverged; do not interpret commits-ahead as ready for release."]
               if compare_result["behind_by"] else [])
        ),
    }


def esc(value):
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("`", "'")


def fmt_tag(info):
    if not info:
        return "—"
    label = esc(info["tag"])
    url = info.get("url")
    return f"[{label}]({url})" if url else label


def create_markdown(payload):
    out = [
        "# ArtCraft Suite — Official upstream vs Android published releases",
        "",
        f"Generated (UTC): {payload['generated_at']}",
        "",
        "**READ ONLY.** This report is metadata only. No APKs built, no production keys accessed, "
        "no tags or releases created, no integration branches updated.",
        "",
        "## Release comparison",
        "",
        "| App | Official stable upstream | Latest published Android | Protected stable Android APK | Release status | Main ahead / behind |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["apps"]:
        if row.get("error"):
            out.append(f"| {row['app'].title()} | — | — | — | ERROR: {esc(row['error'])} | — |")
            continue
        compare = row["upstream_main"]["comparison_to_stable"]
        out.append(
            f"| {row['app'].title()} | {fmt_tag(row['official_stable_upstream'])} | "
            f"{fmt_tag(row['latest_published_android'])} | "
            f"{fmt_tag(row['protected_stable_android_baseline'])} | "
            f"{esc(row['release_gap'])} | {compare.get('ahead_by', '—')} / {compare.get('behind_by', '—')} |"
        )
    out.extend([
        "",
        "## Interpretation",
        "",
        "- **Official stable upstream:** GitHub's latest stable release for Storytold; never a main-branch snapshot.",
        "- **Latest published Android:** newest non-draft GitHub Release whose tag matches the app's Android naming convention.",
        "- **Protected stable Android APK:** newest non-preview, non-draft release with an APK asset. This is the safe baseline; "
        "GitHub release metadata does not verify the signing certificate or actual installed version.",
        "- **Main ahead / behind:** GitHub commit ancestry compared with the official stable tag; "
        "a development commit is not necessarily a new stable feature or compatible Android change.",
        "- **Prerelease detection:** checks both GitHub's prerelease flag and title/tag text, "
        "so a release titled Prerelease isn't silently treated as production stable.",
        "",
        "## Detailed checks",
        "",
    ])
    for row in payload["apps"]:
        app = row["app"]
        out.extend([f"### {app.title()}", ""])
        if row.get("error"):
            out.extend([f"**INCOMPLETE:** {esc(row['error'])}", ""])
            continue
        for label, key in [
            ("Official stable upstream", "official_stable_upstream"),
            ("Latest published Android release", "latest_published_android"),
            ("Protected stable Android APK", "protected_stable_android_baseline"),
        ]:
            rel = row[key]
            if not rel:
                out.append(f"- {label}: **not found**")
            else:
                channel = "prerelease/preview" if rel["is_prerelease"] else "stable"
                out.append(
                    f"- {label}: {fmt_tag(rel)} ({channel}); published {esc(rel['published_at'])}; "
                    f"{len(rel['apk_assets'])} APK asset(s)"
                )
                if key != "official_stable_upstream":
                    for asset in rel["apk_assets"][:5]:
                        out.append(
                            f"  - APK: {esc(asset['name'])}, {asset.get('size_bytes') or 0} bytes"
                            + (f"; SHA-256 digest: {esc(asset['digest'])}" if asset.get("digest") else "")
                        )
        comp = row["upstream_main"]["comparison_to_stable"]
        out.extend([
            f"- Result: **{esc(row['release_gap'])}**",
            f"- Storytold main: [{row['upstream_main']['sha'][:12]}]({row['upstream_main']['url']})",
            f"- [Stable tag vs main comparison]({comp['url']}): status {esc(comp['status'])}; "
            f"{comp['ahead_by']} ahead, {comp['behind_by']} behind",
            "- Last five main commits (these are not necessarily all changes since the stable tag):",
        ])
        for commit in row["upstream_main"]["recent_commits"]:
            out.append(f"  - [{commit['sha'][:10]}]({commit['url']}) "
                       f"({esc(commit['date'])}): {esc(commit['message'])}")
        if row["warnings"]:
            out.append("- Warnings: " + "; ".join(esc(w) for w in row["warnings"]))
        out.append("")
    out.extend([
        "## Guardrails and next action",
        "",
        "Only stable upstream release gaps warrant compatibility review. Preserve every approved "
        "Android-specific feature and the original signing identity in any separate integration work. "
        "Do not merge, build, sign, or publish on the basis of this report alone.",
        "",
        f"Report completeness: **{'COMPLETE' if payload['complete'] else 'INCOMPLETE — one or more checks failed'}**.",
        "",
    ])
    return "\n".join(out)


def self_test():
    def r(tag, title="", prerelease=False, assets=None, published_at="2026-11-11T00:00:00Z"):
        return {"tag_name": tag, "name": title, "draft": False, "prerelease": prerelease,
                "published_at": published_at, "assets": assets if assets is not None else
                [{"name": "app-arm64.apk", "size": 10}]}
    assert android_version(r("gridcraft-v0.18.0-android.1"), "gridcraft") == "0.18.0"
    assert android_version(r("gridcraft-v0.18.0"), "gridcraft") is None
    assert preview(r("gridcraft-v0.18.0-android.1", "ARM64 Prerelease"))
    assert preview(r("photocraft-v0.14.0-android.2-preview.405", "Preview"))
    assert not preview(r("deckcraft-v0.17.0-android.3", "Stable ARM64"))
    assert version_tuple("v0.23.1") == (0, 23, 1)
    rows = [
        r("gridcraft-v0.16.1-android.4", "Stable ARM64", published_at="2026-11-10T00:00:00Z"),
        r("gridcraft-v0.18.0-android.1", "ARM64 Prerelease"),
    ]
    latest, stable = latest_android(rows, "gridcraft")
    assert latest["tag_name"].endswith("v0.18.0-android.1")
    assert stable["tag_name"].endswith("v0.16.1-android.4")
    assert "PREVIEW MATCH ONLY" in gap_status(r("v0.18.0"), latest, stable)
    print("Upstream comparison offline self-tests: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    REPORT_DIR.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    data = {"generated_at": now, "android_repository": ANDROID_REPO,
            "complete": False, "apps": [], "errors": []}
    try:
        android = release_pages(ANDROID_REPO)
    except ApiFailure as exc:
        android = None
        data["errors"].append(str(exc))
    for app in APPS:
        if android is None:
            data["apps"].append({"app": app, "error": "Published Android releases could not be verified"})
            continue
        try:
            data["apps"].append(inspect_app(app, android))
        except (ApiFailure, KeyError, TypeError, IndexError) as exc:
            data["apps"].append({"app": app, "error": str(exc)})
            data["errors"].append(f"{app}: {exc}")
    data["complete"] = not data["errors"] and len(data["apps"]) == len(APPS)
    (REPORT_DIR / "artcraft-upstream-comparison.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPORT_DIR / "artcraft-upstream-comparison.md").write_text(
        create_markdown(data), encoding="utf-8")
    print(f"Compared {len(data['apps'])} apps; complete={data['complete']}. "
          "Wrote Markdown and JSON reports.")
    if not data["complete"]:
        for error in data["errors"]:
            print("INCOMPLETE:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
