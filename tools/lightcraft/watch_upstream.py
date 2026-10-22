#!/usr/bin/env python3
"""Read-only official LightCraft stable upstream check; optionally open one review issue."""
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

UPSTREAM = "storytold/lightcraft"
SUITE = "KosmosSG/artcraft-android"
TOKEN = os.environ["GH_TOKEN"]
HEADERS = {
    "Authorization": "Bearer " + TOKEN,
    "Accept": "application/vnd.github+json",
    "User-Agent": "lightcraft-upstream-review",
    "X-GitHub-Api-Version": "2022-11-28",
}

def github(path, payload=None):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers=HEADERS,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def tag_commit(tag):
    obj = github("/repos/" + UPSTREAM + "/git/ref/tags/" + urllib.parse.quote(tag, safe=""))["object"]
    if obj["type"] == "tag":
        obj = github("/repos/" + UPSTREAM + "/git/tags/" + obj["sha"])["object"]
    if obj["type"] != "commit" or not re.fullmatch(r"[a-f0-9]{40}", obj["sha"]):
        raise RuntimeError("Unresolved or invalid official release tag")
    return obj["sha"]

lock = json.loads(Path("review/tools/lightcraft/source-lock.json").read_text())
if lock["source"]["repository"] != UPSTREAM:
    raise RuntimeError("Unexpected source-lock repository")
pin, pin_sha = lock["source"]["tag"], lock["source"]["commit"]
if not re.fullmatch(r"v\d+\.\d+\.\d+", pin) or tag_commit(pin) != pin_sha:
    raise RuntimeError("Reviewed LightCraft tag/commit changed; manual security review required")
releases = github("/repos/" + UPSTREAM + "/releases?per_page=100")
stable = []
for entry in releases:
    tag = entry.get("tag_name", "")
    if not entry.get("draft") and not entry.get("prerelease") and re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        stable.append((tuple(int(x) for x in tag[1:].split(".")), tag, entry))
if not stable:
    raise RuntimeError("No official stable LightCraft releases found")
version, latest, entry = max(stable)
sha = tag_commit(latest)
pin_version = tuple(int(x) for x in pin[1:].split("."))
if version < pin_version:
    raise RuntimeError("Official stable history is older than reviewed pin")
newer = version > pin_version
report = {
    "official_upstream": UPSTREAM,
    "reviewed_source": {"tag": pin, "commit": pin_sha},
    "latest_stable": {"tag": latest, "commit": sha, "url": entry["html_url"]},
    "new_release_requires_review": newer,
    "source_changed": False,
    "unattended_merge_enabled": False,
    "automatic_apk_build_or_release_enabled": False,
}
if newer:
    title = f"Review LightCraft upstream {latest} for Android"
    found = False
    for page in range(1, 101):
        issues = github(f"/repos/{SUITE}/issues?state=all&per_page=100&page={page}")
        if any(i.get("title") == title and "pull_request" not in i for i in issues):
            found = True
            break
        if len(issues) < 100:
            break
    else:
        raise RuntimeError("Cannot safely search full issue history; refusing duplicate")
    if found:
        report["issue"] = "previously created"
    else:
        body = (
            f"New official stable release: {entry['html_url']}\n"
            f"Verified official tag commit: `{sha}`\n\n"
            f"Previously reviewed v{lock['official_version']} source commit: `{pin_sha}` (PR #16).\n\n"
            "Human review required: Android API/build compatibility, RAW processing, SAF import/export, "
            "approved icon, text/watermark fonts, shortcut mapping, touch/tablet layout, "
            "GPU diagnostics, updater, versionCode, signer continuity, licenses, device testing.\n\n"
            "**Review ticket only. No code update, merge, APK build, signing change, or release is authorized.**"
        )
        created = github(f"/repos/{SUITE}/issues", {"title": title, "body": body})
        report["issue"] = created["html_url"]
Path("lightcraft-upstream-report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
    summary.write("### Official LightCraft stable upstream review\n\n")
    summary.write(f"- Latest stable: {latest} (`{sha}`)\n")
    summary.write(f"- Reviewed pin: {pin} (`{pin_sha}`)\n")
    summary.write(f"- New release requires human review: **{str(newer).lower()}**\n")
    summary.write("- No automatic code merge, production APK build, key change, or public release.\n")
    if newer:
        summary.write(f"- Review ticket: {report['issue']}\n")
