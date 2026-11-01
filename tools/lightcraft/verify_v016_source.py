#!/usr/bin/env python3
"""Read-only provenance check for an already cloned official LightCraft v0.16.0 checkout."""
import json
import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / "configs/upstream/lightcraft-v016.json").read_text())

def git(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

def verify(checkout):
    checkout = pathlib.Path(checkout).resolve()
    if not (checkout / ".git").exists():
        raise ValueError("Expected a standalone git checkout, not an APK or exported source tree")
    expected = LOCK["tag_commit"]
    if git(checkout, "rev-parse", "HEAD") != expected:
        raise ValueError("HEAD differs from verified official stable tag commit")
    if git(checkout, "rev-parse", "refs/tags/" + LOCK["stable_tag"] + "^{commit}") != expected:
        raise ValueError("Local stable tag does not resolve to the locked official commit")
    if git(checkout, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked source files are modified")
    cargo = tomllib.loads((checkout / "Cargo.toml").read_text())
    pkg = cargo["workspace"]["package"]
    if pkg["version"] != LOCK["upstream_workspace_version"]:
        raise ValueError("Unexpected upstream workspace version")
    if pkg.get("rust-version") != "1.95":
        raise ValueError("Recheck changed upstream Rust MSRV before Android integration")
    if pkg.get("repository") != "https://github.com/storytold/lightcraft":
        raise ValueError("Unexpected upstream repository identity")
    print("PASS: LightCraft official v0.16.0 source identity verified (NOT an Android build)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 tools/lightcraft/verify_v016_source.py /path/to/tagged/lightcraft")
    try:
        verify(sys.argv[1])
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit("STOP: " + str(exc))
