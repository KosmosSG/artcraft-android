#!/usr/bin/env python3
"""Fail-closed, read-only provenance check for official lightcraft v0.17.0 source."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / "configs/upstream/lightcraft-v017.json").read_text())

def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()

def verify(path):
    source = Path(path).resolve()
    if not (source / ".git").exists():
        raise ValueError("Expected a standalone tagged Git checkout")
    expected = LOCK["tag_commit"]
    if git(source, "rev-parse", "HEAD") != expected:
        raise ValueError("Checkout HEAD differs from official stable commit")
    if git(source, "rev-parse", "refs/tags/" + LOCK["stable_tag"] + "^{commit}") != expected:
        raise ValueError("Local stable tag differs from locked commit")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked upstream checkout is dirty")
    package = tomllib.loads((source / "Cargo.toml").read_text())["workspace"]["package"]
    if package["version"] != LOCK["upstream_workspace_version"]:
        raise ValueError("Unexpected upstream workspace version")
    if package.get("repository") != "https://github.com/storytold/lightcraft":
        raise ValueError("Wrong upstream repository")
    if package.get("rust-version") != "1.95":
        raise ValueError("Rust MSRV changed; review Android builder")
    print("PASS: official lightcraft v0.17.0 source identity only; Android port NOT verified")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/lightcraft/verify_v017_source.py /path/to/tagged/lightcraft")
    try:
        verify(sys.argv[1])
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit("STOP: " + str(exc))
