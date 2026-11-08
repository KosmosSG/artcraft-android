#!/usr/bin/env bash
# PDFCraft Android.6: capture lifecycle transitions without clearing user data.
set -euo pipefail
PKG="com.artcraft.pdfcraft.v019test6"
OUT="${1:-$HOME/Downloads/pdfcraft-lifecycle-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd -P)"
adb get-state | grep -qx device || { echo "ADB device unavailable"; exit 1; }
echo "Collecting lifecycle evidence for $PKG in $OUT"
adb shell pidof "$PKG" > "$OUT/pid-before.txt" || true
adb shell dumpsys activity activities > "$OUT/activities-before.txt"
adb logcat -c
echo "Now: launch PDFCraft, open a PDF, press Ctrl+Q, attempt to relaunch; DO NOT force stop. Press ENTER here afterward."
read -r _
adb shell pidof "$PKG" > "$OUT/pid-after.txt" || true
adb shell ps -A > "$OUT/processes-after.txt"
adb shell dumpsys activity activities > "$OUT/activities-after.txt"
adb shell dumpsys activity processes > "$OUT/activity-processes-after.txt"
adb logcat -d -b main,system,crash,events -v threadtime > "$OUT/logcat.txt"
grep -Ei 'pdfcraft|AndroidRuntime|ActivityTaskManager|ActivityManager|NativeActivity|zygote|tombstone|FATAL EXCEPTION|PDFCraftLifecycle|onDestroy|onStop|onPause' "$OUT/logcat.txt" > "$OUT/lifecycle-filtered.txt" || true
python3 - "$OUT" <<'PY'
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
folder = Path(sys.argv[1])
archive = folder.with_suffix(".zip")
with ZipFile(archive, "w", ZIP_DEFLATED) as output:
    for file in sorted(folder.glob("*.txt")):
        output.write(file, arcname=file.name)
print("Diagnostic ZIP:", archive)
PY
echo "Done. Review and upload the ZIP in Downloads; it may include device/app details."
