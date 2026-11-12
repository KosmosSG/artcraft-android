#!/usr/bin/env python3
"""One-time, pinned GitHub Release cleanup. Never delete Git refs/tags."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = "KosmosSG/artcraft-android"
BRANCH = "maintenance/release-retention-3-stable-20261112"
APPS = ["photocraft","vectorcraft","designcraft","effectcraft","filmcraft","lightcraft","pdfcraft","wordcraft","deckcraft","gridcraft"]
EXPECTED_LATEST = json.loads(r'''{"photocraft":"photocraft-v0.22.0-android.3","vectorcraft":"vectorcraft-v0.23.0-android.7","designcraft":"designcraft-v0.19.0-android.1","effectcraft":"effectcraft-v0.23.1-android.1","filmcraft":"filmcraft-v0.19.0-android.1","lightcraft":"lightcraft-v0.20.0-android.1","pdfcraft":"pdfcraft-v0.20.0-android.4","wordcraft":"wordcraft-v0.17.0-android.1","deckcraft":"deckcraft-v0.17.0-android.3","gridcraft":"gridcraft-v0.18.0-android.1"}''')
SNAPSHOT = json.loads(r'''{"416870734":["photocraft-v0.10.0",false,false,false],"417050306":["photocraft-v0.10.1",false,false,false],"417463501":["photocraft-v0.10.2",false,false,false],"417972095":["photocraft-v0.10.3",false,false,false],"418082076":["photocraft-v0.10.4",false,false,false],"419318616":["photocraft-v0.10.0-android.2",false,false,true],"421422571":["photocraft-v0.12.0-android.1",false,false,false],"421474817":["pdfcraft-v0.12.0-android.1",false,false,false],"421500894":["pdfcraft-v0.12.1-android.1",false,false,false],"421594358":["designcraft-v0.12.0-android.2",false,false,true],"421602406":["vectorcraft-v0.14.0-android.5",false,false,false],"421925853":["lightcraft-v0.11.0-android.3",true,false,false],"422018204":["lightcraft-v0.11.0-android.4",true,false,false],"422052822":["lightcraft-v0.11.0-android.5",true,false,false],"422126151":["lightcraft-v0.11.0-android.6",false,false,false],"422444509":["effectcraft-v0.16.0-android.2",false,false,false],"422465989":["pdfcraft-v0.12.1-android.2",false,false,false],"422466548":["wordcraft-v0.9.0-android.3",false,false,true],"423113340":["photocraft-v0.12.0-android.2",false,false,false],"423113881":["vectorcraft-v0.14.0-android.8",false,false,false],"423114230":["designcraft-v0.12.0-android.3",false,false,true],"423150741":["pdfcraft-v0.12.1-android.3",false,false,false],"423150786":["deckcraft-v0.9.0-android.2",false,false,false],"423151026":["wordcraft-v0.9.0-android.4",false,false,false],"423152437":["effectcraft-v0.16.0-android.4",false,false,false],"423161233":["lightcraft-v0.11.0-android.7",true,false,false],"423280051":["lightcraft-v0.11.0-android.8",false,false,false],"423335156":["deckcraft-v0.9.0-android.3",false,false,false],"423482392":["vectorcraft-v0.14.0-android.9",true,false,false],"423507079":["vectorcraft-v0.14.0-android.10",false,false,false],"423827483":["gridcraft-v0.11.1-android.2",false,false,false],"423955577":["effectcraft-v0.16.0-android.3-preview.40284755992",true,false,false],"423985082":["effectcraft-v0.16.0-android.3-preview.40289333285",true,false,false],"424025742":["photocraft-v0.14.0-android.1-preview.40293846691",true,false,false],"424075888":["photocraft-v0.14.0-android.1-preview.40300751061",true,false,false],"424262127":["effectcraft-v0.16.0-android.3-preview.40326570342",true,false,false],"424376059":["effectcraft-v0.16.0-android.3-preview.40341024386",true,false,false],"424406265":["effectcraft-v0.16.0-android.3-preview.40345515710",true,false,false],"424421424":["vectorcraft-v0.14.0-android.11",false,false,false],"424435735":["photocraft-v0.14.0-android.1-preview.40348951736",true,false,false],"424474841":["photocraft-v0.14.0-android.1-preview.40354111525",true,false,false],"424498721":["photocraft-v0.14.0-android.1-preview.40358277612",true,false,false],"424898079":["photocraft-v0.14.0-android.1-preview.40422186503",true,false,false],"424942587":["effectcraft-v0.16.0-android.5",false,false,false],"425268772":["designcraft-v0.12.0-android.4",false,false,true],"425601345":["photocraft-v0.14.0-android.1-preview.40523180826",true,false,false],"425656264":["photocraft-v0.14.0-android.1-preview.40530378907",true,false,false],"425719127":["photocraft-v0.14.0-android.1",false,false,false],"426107199":["filmcraft-v0.10.0-android.2",false,false,false],"426806814":["designcraft-v0.12.0-android.5",false,false,true],"428130176":["designcraft-v0.12.0-android.8",false,false,false],"429299032":["gridcraft-v0.11.1-android.4",false,false,false],"430139882":["vectorcraft-v0.14.0-android.13",false,false,false],"430164420":["effectcraft-v0.16.0-android.8",false,false,false],"430336805":["photocraft-v0.14.1-v2-preview",true,false,false],"430336841":["photocraft-v0.14.0-android.2-ai-v2-preview",true,false,false],"430389162":["deckcraft-v0.9.0-android.4",false,false,false],"430505652":["photocraft-v0.14.0-android.4-ai-v2-fontscan-preview",true,false,false],"430521919":["photocraft-v0.14.0-android.4",false,false,false],"430750685":["wordcraft-v0.9.0-android.6",false,false,false],"430757340":["deckcraft-v0.9.0-android.4-dcs-fix",false,false,false],"430937500":["gridcraft-v0.11.1-android.4-ctrlw-dcs-fix",false,false,false],"430939950":["designcraft-v0.12.0-android.9",false,false,false],"431135824":["filmcraft-v0.10.0-android.5",false,false,false],"432818907":["deckcraft-v0.14.1-android.16",false,false,false],"432918165":["deckcraft-v0.14.1-android.17",false,false,false],"433413098":["deckcraft-v0.15.0-android.1",false,false,false],"433414790":["gridcraft-v0.15.0-android.1-ctrlw-dcs-fix",false,false,false],"434065970":["filmcraft-v0.17.0-android.1",false,false,false],"435373402":["wordcraft-v0.14.0-android.8",false,false,false],"435517465":["photocraft-v0.20.1-android.10",false,false,false],"436037275":["photocraft-v0.20.2-android.2",false,false,false],"436756161":["gridcraft-v0.16.1-android.3",false,false,false],"436759472":["wordcraft-v0.15.2-android.2",false,false,false],"437430367":["gridcraft-v0.16.1-android.4",false,false,false],"437431865":["wordcraft-v0.15.2-android.3",false,false,false],"437634328":["wordcraft-v0.15.2-android.6",false,false,false],"437662096":["deckcraft-v0.16.0-android.3",false,false,false],"438376838":["wordcraft-v0.15.2-android.11",false,false,false],"438380395":["effectcraft-v0.21.0-android.15",false,false,false],"438404103":["pdfcraft-v0.19.0-android.6",false,false,false],"438655461":["designcraft-v0.17.2-android.5",false,false,false],"438823151":["lightcraft-v0.18.0-android.1",false,false,false],"438999997":["photocraft-v0.21.0-android.5",false,false,false],"440080280":["designcraft-v0.19.0-android.1",false,false,true],"440150996":["vectorcraft-v0.23.0-android.7",false,false,false],"440167597":["effectcraft-v0.23.1-android.1",false,false,false],"440183094":["lightcraft-v0.20.0-android.1",false,false,false],"440185357":["wordcraft-v0.17.0-android.1",false,false,false],"440204974":["pdfcraft-v0.20.0-android.1",false,false,false],"440217681":["gridcraft-v0.18.0-android.1",false,false,false],"440598753":["pdfcraft-v0.20.0-android.4",false,false,false],"440606477":["deckcraft-v0.17.0-android.3",false,false,false],"441578212":["filmcraft-v0.19.0-android.1",false,false,false],"441604686":["photocraft-v0.22.0-android.3",false,false,false]}''')
EXPECTED_DELETE_IDS = set(json.loads(r'''[437431865,436759472,435373402,435517465,433414790,432918165,432818907,430750685,430521919,430937500,430757340,430389162,430505652,430336841,429299032,428130176,425719127,424942587,425656264,425601345,423827483,426107199,424898079,424498721,424474841,424435735,424075888,424025742,424406265,424376059,424262127,423985082,423955577,423507079,423335156,423482392,423151026,423113881,423113340,423150741,422465989,423152437,423150786,423161233,421602406,421500894,421474817,422126151,422444509,422052822,422018204,421925853,421422571,418082076,417972095,417463501,417050306,416870734,430336805]'''))
EXPECTED_KEEP_IDS = set(json.loads(r'''[441604686,438999997,436037275,440150996,430139882,424421424,440080280,438655461,430939950,440167597,438380395,430164420,441578212,434065970,431135824,440183094,438823151,423280051,440598753,440204974,438404103,440185357,438376838,437634328,440606477,437662096,433413098,440217681,437430367,436756161,426806814,425268772,423114230,422466548,421594358,419318616]'''))

def stop(message):
    raise SystemExit("STOP: " + message)

if os.environ.get("GITHUB_REPOSITORY") != REPO:
    stop("repository mismatch")
if os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH:
    stop("unexpected branch")
if os.environ.get("ARTCRAFT_RELEASE_PRUNE_APPROVED") != "authorized-nov-12-2026":
    stop("explicit approval gate missing")
TOKEN = os.environ.get("GH_TOKEN", "")
if not TOKEN:
    stop("GitHub Actions token missing")
BASE = "https://api.github.com/repos/" + REPO

def api(path, method="GET"):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ArtCraft-Owner-Approved-Release-Retention",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            data = response.read()
            if method == "DELETE":
                if response.status != 204:
                    stop("release deletion returned unexpected status")
                return None
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        stop(f"GitHub API {method} failed with HTTP {exc.code} at path {path}")

def all_releases():
    out = []
    for page in range(1, 8):
        chunk = api(f"/releases?per_page=100&page={page}")
        if not isinstance(chunk, list):
            stop("unexpected GitHub releases response")
        out.extend(chunk)
        if len(chunk) < 100:
            return out
    stop("pagination exceeded safety cap")

def has_update_manifest(release):
    return any(str(asset.get("name", "")).lower().endswith(("-update.json", "_update.json"))
               for asset in release.get("assets", []))

releases = all_releases()
actual = {str(r["id"]): r for r in releases}
if set(actual) != set(SNAPSHOT):
    stop("release inventory changed since owner-approved audit (no releases modified)")
for id_str, expected in SNAPSHOT.items():
    r = actual[id_str]
    current = [r.get("tag_name"), bool(r.get("prerelease")), bool(r.get("draft")), has_update_manifest(r)]
    if current != expected:
        stop(f"release metadata drift for {id_str}: {r.get('tag_name')}")

protected = set()
for app in APPS:
    stable = sorted(
        (r for r in releases if r["tag_name"].lower().startswith(app + "-")
         and not r.get("prerelease") and not r.get("draft")),
        key=lambda r: r.get("published_at") or r.get("created_at") or "",
        reverse=True,
    )
    if len(stable) < 3 or stable[0]["tag_name"] != EXPECTED_LATEST[app]:
        stop(f"stable baseline changed for {app}")
    protected.update(r["id"] for r in stable[:3])
protected.update(r["id"] for r in releases if r.get("draft") or has_update_manifest(r))
if protected != EXPECTED_KEEP_IDS:
    stop("protected release IDs diverge from approved plan")
target_ids = set(int(x) for x in actual).difference(protected)
if target_ids != EXPECTED_DELETE_IDS or len(target_ids) != 59:
    stop("candidate deletion list differs from the pinned 59 releases")
print("PRECHECK PASS: 95 public releases, 36 retained, 59 eligible for deletion.")
print("No Git tags, branches, source commits, signing keys or update manifests are deleted.")
for app in APPS:
    print(f"  {app}: newest protected stable = {EXPECTED_LATEST[app]}")

summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as report:
        report.write("# ArtCraft Release Retention Cleanup\n\n")
        report.write("Approved: retain 3 stable releases for each of 10 apps,")
        report.write(" plus 6 legacy update-manifest release hosts.\n\n")
        report.write("Pinned audit: 95 releases. Deletion plan: 59 releases.\n\n")
        report.write("| App | Latest retained stable |\n|---|---|\n")
        for app in APPS:
            report.write(f"| {app} | {EXPECTED_LATEST[app]} |\n")

# Commit-time exact allowlist. No branch, tag, APK build, or updater metadata writes.
deleted = 0
for release in sorted((r for r in releases if r["id"] in target_ids), key=lambda x: x["tag_name"]):
    checked = api("/releases/" + str(release["id"]))
    if checked.get("tag_name") != release["tag_name"] or checked.get("draft") != release.get("draft"):
        stop("release changed before delete: " + release["tag_name"])
    print("Deleting release only (retaining Git tag):", release["tag_name"], flush=True)
    api("/releases/" + str(release["id"]), method="DELETE")
    deleted += 1
    time.sleep(0.8)

remaining = all_releases()
remain_ids = {r["id"] for r in remaining}
if remain_ids != protected:
    stop(f"post-cleanup mismatch; deleted {deleted}, remaining {len(remaining)}")
print(f"SUCCESS: deleted {deleted} old GitHub releases; {len(remaining)} protected release entries remain.")
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as report:
        report.write(f"\n**Success:** removed {deleted} obsolete Releases, retained {len(remaining)}. Git tags unchanged.\n")
