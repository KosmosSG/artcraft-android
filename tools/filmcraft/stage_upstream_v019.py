#!/usr/bin/env python3
"""Stage version-specific verification ONLY in disposable CI checkout.

Keep the installed FilmCraft android.5 icon resources, package ID, native
feature overlay, and signing identity untouched. This only changes verification
metadata in the CI copy; a separate reviewed production procedure is required.
"""
from pathlib import Path
import json
import sys

OLD_VERSION = "0.10.0-android.5"
NEW_VERSION = "0.19.0-android.2-test"
OLD_CODE = 1000005
NEW_CODE = 1900002
PINNED_UPSTREAM_SHA = "d1af238bba9fc814487c81e47b53543dff435c09"

def stage(suite: Path) -> None:
    manifest = suite / "tools/approved-branding/assets/manifest.json"
    verifier = suite / "tools/filmcraft/verify_android_features_apk_v019.py"
    version_patch = suite / "tools/filmcraft/stage_upstream_v019_variant.py"
    if not all(p.is_file() for p in (manifest, verifier, version_patch)):
        raise ValueError("Missing FilmCraft review artifacts; refusing to stage")
    cfg = json.loads(manifest.read_text())
    if (cfg.get("app"), cfg.get("package"), cfg.get("version_name"),
        cfg.get("version_code"), cfg.get("previous_version_code")) != (
        "filmcraft", "com.artcraft.filmcraft", OLD_VERSION, OLD_CODE, 1000004
    ):
        raise ValueError("FilmCraft android.5 approved baseline changed; review before port")
    src = verifier.read_text()
    old = '("com.artcraft.filmcraft", "1000005", "0.10.0-android.5")'
    new = '("com.artcraft.filmcraft.test", "1900002", "0.19.0-android.2-test")'
    if src.count(old) != 1 or new in src:
        raise ValueError("Compiled feature verifier drifted; review before port")
    compiled = src.replace(old, new, 1)
    compile(compiled, str(verifier), "exec")
    cfg["version_name"] = NEW_VERSION
    cfg["package"] = "com.artcraft.filmcraft.test"
    cfg["version_code"] = NEW_CODE
    cfg["previous_version_code"] = 1700001
    # All approved image hashes and SAF, keyboard, menu functionality stay intact.
    manifest.write_text(json.dumps(cfg, indent=2) + "\n")
    verifier.write_text(compiled)
    print("PASS: isolated FilmCraft v0.19.0 version/certificate-independent checks staged")

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: stage_upstream_v019.py /workspace/suite")
    root = Path(sys.argv[1]).resolve()
    if root.name != "suite" or not (root / ".github").is_dir():
        raise SystemExit("STOP: expected disposable GitHub Actions suite checkout")
    stage(root)

if __name__ == "__main__":
    main()
