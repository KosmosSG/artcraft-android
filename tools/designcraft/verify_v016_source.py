#!/usr/bin/env python3
"""Read-only, fail-closed provenance verification of Storytold DesignCraft v0.16.0."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / "configs/upstream/designcraft-v016.json").read_text())

def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

def verify(path):
    checkout = Path(path).resolve()
    if not (checkout / ".git").exists():
        raise ValueError("Standalone official tagged Git checkout required")
    expected = LOCK["tag_commit"]
    if git(checkout, "rev-parse", "HEAD") != expected:
        raise ValueError("HEAD differs from official stable tag")
    if git(checkout, "rev-parse", "refs/tags/" + LOCK["stable_tag"] + "^{commit}") != expected:
        raise ValueError("Local tag does not match official stable commit")
    if git(checkout, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked source checkout is dirty")
    pkg = tomllib.loads((checkout / "Cargo.toml").read_text())["workspace"]["package"]
    if pkg["version"] != LOCK["upstream_workspace_version"]:
        raise ValueError("Unexpected upstream workspace version")
    if pkg.get("repository") != "https://github.com/storytold/designcraft":
        raise ValueError("Unexpected official repository identity")
    if pkg.get("rust-version") != "1.95":
        raise ValueError("Rust MSRV changed; re-audit Android builder")
    print("PASS: official DesignCraft v0.16.0 source provenance only; Android port NOT verified")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/designcraft/verify_v016_source.py /path/to/tagged/designcraft")
    try:
        verify(sys.argv[1])
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit("STOP: " + str(exc))
