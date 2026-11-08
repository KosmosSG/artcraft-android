#!/usr/bin/env bash
# PDFCraft Android.6: capture lifecycle transitions without clearing user data.
set -euo pipefail
PKG="com.artcraft.pdfcraft.v019test6"
OUT="${1:-pdfcraft-lifecycle-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
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
echo "Done. Upload logcat.txt, lifecycle-filtered.txt, pid-before.txt, pid-after.txt, activities-after.txt and activity-processes-after.txt. Files may include device/app details; review before sharing."
