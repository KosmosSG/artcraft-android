#!/usr/bin/env python3
"""Fail-closed, read-only provenance gate for a tagged PDFCraft v0.16.1 checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / "configs/upstream/pdfcraft-v0161.json").read_text())

def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()

def check(path):
    source = Path(path).resolve()
    if not (source / ".git").exists():
        raise ValueError("Standalone tagged git checkout required")
    sha = LOCK["tag_commit"]
    if git(source, "rev-parse", "HEAD") != sha:
        raise ValueError("HEAD does not match official stable commit")
    if git(source, "rev-parse", "refs/tags/" + LOCK["stable_tag"] + "^{commit}") != sha:
        raise ValueError("Tag mismatch")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked checkout is dirty")
    pkg = tomllib.loads((source / "Cargo.toml").read_text())["workspace"]["package"]
    if pkg["version"] != LOCK["upstream_workspace_version"]:
        raise ValueError("Unexpected workspace version")
    if pkg.get("repository") != "https://github.com/storytold/pdfcraft":
        raise ValueError("Wrong upstream repository")
    if pkg.get("rust-version") != "1.95":
        raise ValueError("Rust MSRV changed; review Android builder")
    print("PASS: official PDFCraft v0.16.1 source provenance only; Android port NOT validated")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/pdfcraft/verify_v0161_source.py /path/to/tagged/pdfcraft")
    try:
        check(sys.argv[1])
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit("STOP: " + str(exc))
