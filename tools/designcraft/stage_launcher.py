"""Run the pinned builder's launcher generator without compiling or signing an APK."""
from pathlib import Path
import subprocess
import sys


def stage(builder):
    root = Path(builder).resolve()
    source = root / "source/designcraft"
    script = (root / "lib/build-common.sh").read_text()
    anchor = '    python3 - "$ROOT" "$SRC" "$APP" "$TITLE" "$TARGET_SDK" "$APPNAME" "$PACKAGENAME" "$APPICON" <<\'PY\'\n'
    if script.count(anchor) != 1:
        raise ValueError("Pinned launcher generator changed")
    generator = script.split(anchor, 1)[1].split("\nPY\n", 1)[0]
    subprocess.run([sys.executable, "-", str(root), str(source), "designcraft", "DesignCraft", "35",
                    "DesignCraft", "com.artcraft.designcraft", str(root / "dc-icon.png")],
                   input=generator, text=True, check=True)
    subprocess.run([sys.executable, str(root / "designcraft-support/patch_launcher.py"),
                    str(source / "apps/designcraft-android")], check=True)


if __name__ == "__main__":
    stage(sys.argv[1])
