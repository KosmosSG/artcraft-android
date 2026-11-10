#!/usr/bin/env python3
"""Fail-closed FilmCraft 0.19 test-version staging in an isolated Android builder.

This patch changes version metadata only. Independently verify that the final
manifest/application IDs and provider authorities use the separately installable
test package. Do NOT use this script to modify production-signing workflows.
"""
from pathlib import Path
import sys

ANCHOR = "    code = version_code(version)\n"
INSERT = """    code = version_code(version)
    # Only the isolated FilmCraft upstream v0.19.0 ARM64 test builder.
    if app == "filmcraft":
        import os
        if version != "0.19.0":
            raise SystemExit("STOP: FilmCraft upstream checkout is not v0.19.0")
        if os.environ.get("FILMCRAFT_ANDROID_VERSION_NAME") != "0.19.0-android.2-test":
            raise SystemExit("STOP: incorrect FilmCraft temporary version name")
        if os.environ.get("FILMCRAFT_EPHEMERAL_VERSION_CODE") != "1900002":
            raise SystemExit("STOP: incorrect FilmCraft temporary version code")
        if os.environ.get("FILMCRAFT_TEST_PACKAGE") != "com.artcraft.filmcraft.test":
            raise SystemExit("STOP: this variant requires a separate install package")
        code = 1900002
"""

def patch_text(source: str) -> str:
    if source.count(ANCHOR) != 1 or INSERT in source:
        raise ValueError("STOP: pinned Android builder version hook drifted or already patched")
    updated = source.replace(ANCHOR, INSERT, 1)
    compile(updated, "android_project.py", "exec")
    return updated

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: stage_upstream_v019_variant.py /disposable/filmcraft-builder/lib/android_project.py")
    path = Path(sys.argv[1]).resolve()
    if path.name != "android_project.py" or path.parent.name != "lib" or "filmcraft-builder" not in path.parts:
        raise SystemExit("STOP: only a disposable FilmCraft builder can be changed")
    path.write_text(patch_text(path.read_text()))
    print("PASS: isolated FilmCraft v0.19.0 test version staged")

if __name__ == "__main__":
    main()
