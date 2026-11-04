#!/usr/bin/env python3
"""FilmCraft v0.16.0 ephemeral version override, isolated from android.5.

Only patches a disposable pinned builder used for the v0.16.0 compatibility
candidate. Never edits the shared suite or any release/signing workflow.
"""
from pathlib import Path
import sys

ANCHOR = "    code = version_code(version)\n"
INSERT = """    code = version_code(version)
    # Compatibility candidate only. Do not reserve a production versionCode.
    if app == "filmcraft":
        import os
        if version != "0.16.0":
            raise SystemExit("STOP: upstream version must be FilmCraft v0.16.0")
        version = os.environ.get("FILMCRAFT_ANDROID_VERSION_NAME", "")
        if version != "0.16.0-android.1":
            raise SystemExit("STOP: invalid v0.16 FilmCraft candidate versionName")
        value = os.environ.get("FILMCRAFT_EPHEMERAL_VERSION_CODE", "")
        if value != "1600001":
            raise SystemExit("STOP: v0.16 compatibility candidate only uses provisional 1600001")
        code = int(value)
"""

def patch_text(source: str) -> str:
    if source.count(ANCHOR) != 1 or INSERT in source:
        raise ValueError("STOP: pinned builder version hook drifted or already patched")
    result = source.replace(ANCHOR, INSERT, 1)
    compile(result, "android_project.py", "exec")
    return result

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: stage_upstream_v016_variant.py /disposable/filmcraft-builder/lib/android_project.py")
    path = Path(sys.argv[1]).resolve()
    if path.name != "android_project.py" or path.parent.name != "lib" or "filmcraft-builder" not in path.parts:
        raise SystemExit("STOP: not a disposable FilmCraft builder")
    path.write_text(patch_text(path.read_text()))
    print("PASS: provisional v0.16.0-android.1 version staged in disposable builder")

if __name__ == "__main__":
    main()
