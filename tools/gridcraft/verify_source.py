#!/usr/bin/env python3
"""Read-only provenance and release policy check for the isolated GridCraft port."""
import argparse
import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

LOCK = Path(__file__).with_name("source-lock.json")
UPSTREAM = "storytold/gridcraft"
REF_BUILDER = "MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af"
ICON_SHA = "8c0db50831bd715812212c04f156029cfeabd1be82cf5bd777c9db5547063d19"

def validate(data):
    assert data["app"] == "gridcraft"
    assert data["product_name"] == "GridCraft"
    assert data["upstream_repository"] == UPSTREAM
    assert data["official_version"] == "0.9.0"
    assert data["official_release_tag"] == "v" + data["official_version"]
    assert re.fullmatch(r"[a-f0-9]{40}", data["official_release_commit"])
    assert type(data["android_revision"]) is int and data["android_revision"] >= 1
    assert data["version_name"] == data["official_version"] + "-android." + str(data["android_revision"])
    assert data["intended_release_apk"] == "gridcraft-" + data["version_name"] + ".apk"
    assert data["production_package"] == "com.artcraft.gridcraft"
    assert data["target_abi"] == "arm64-v8a"
    assert data["implementation_reference"] == REF_BUILDER
    assert data["icon_original_name"] == "Glossy Green Xc App Icon(1).png"
    assert data["icon_source_sha256"] == ICON_SHA
    assert data["icon_lettering"] == "Xc"
    assert data["icon_intended_repository_path"] == "assets/gridcraft/launcher-source.png"
    assert type(data["icon_committed"]) is bool
    if data["icon_committed"]:
        import hashlib
        icon = Path(__file__).resolve().parents[2] / data["icon_intended_repository_path"]
        assert icon.is_file(), "source icon marked committed but missing"
        assert hashlib.sha256(icon.read_bytes()).hexdigest() == ICON_SHA, "source icon checksum mismatch"
    assert data["version_code_reserved"] is None or (type(data["version_code_reserved"]) is int and data["version_code_reserved"] > 0)
    cert = data["permanent_signing_certificate_sha256"]
    assert cert is None or re.fullmatch(r"[0-9a-fA-F]{64}", cert)
    assert type(data["permanent_key_backup_verified"]) is bool
    assert type(data["build_approved"]) is bool
    assert type(data["publish_approved"]) is bool
    if data["publish_approved"]:
        assert data["icon_committed"]
        assert data["version_code_reserved"] is not None
        assert cert is not None and data["permanent_key_backup_verified"]
        assert data["build_approved"]

def get_json(url):
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "GridCraft-source-audit/1"})
    with urllib.request.urlopen(request, timeout=15) as r:
        return json.load(r)

def check_online(data):
    base = "https://api.github.com/repos/" + UPSTREAM
    release = get_json(base + "/releases/tags/" + data["official_release_tag"])
    assert release["tag_name"] == data["official_release_tag"]
    assert not release["draft"] and not release["prerelease"], "tag is not a stable release"
    ref = get_json(base + "/git/ref/tags/" + data["official_release_tag"])["object"]
    if ref["type"] == "tag":  # Follow annotated tags to the underlying commit.
        ref = get_json(ref["url"])["object"]
    assert ref["type"] == "commit"
    assert ref["sha"] == data["official_release_commit"], "upstream tag does not match the approved commit"
    source = urllib.request.Request(
        "https://raw.githubusercontent.com/" + UPSTREAM + "/" + ref["sha"] + "/Cargo.toml",
        headers={"User-Agent": "GridCraft-source-audit/1"},
    )
    with urllib.request.urlopen(source, timeout=15) as r:
        manifest = tomllib.loads(r.read().decode("utf-8"))
    assert manifest["workspace"]["package"]["version"] == data["official_version"]
    return {"official_stable_release_confirmed": True, "tag_commit_verified": True, "workspace_version_verified": True}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true", help="Check GitHub's stable release and immutable tag without modifying anything")
    args = parser.parse_args()
    data = json.loads(LOCK.read_text())
    validate(data)
    result = {"app": data["app"], "version_name": data["version_name"], "source_commit": data["official_release_commit"],
              "policy_valid": True, "source_icon_in_repository": data["icon_committed"],
              "version_code_reserved": data["version_code_reserved"] is not None,
              "permanent_signing_verified": data["permanent_signing_certificate_sha256"] is not None and data["permanent_key_backup_verified"],
              "build_approved": data["build_approved"], "publish_approved": data["publish_approved"]}
    if args.online:
        result.update(check_online(data))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, KeyError, ValueError, OSError) as exc:
        print("GridCraft audit FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)
