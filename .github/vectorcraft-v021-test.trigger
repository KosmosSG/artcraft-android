VectorCraft v0.21.0-android.3 — one owner-authorized ARM64 test build
Preserve stable vectorcraft-v0.14.0-android.13; official v0.21.0 base.
Fix: launcher safe padding in adaptive and legacy icon resources.
Fix: click existing top-left Vc app icon; no duplicate Vc word menu.
Fix: brand maroon Android launch window and native cover through first GPU frame.
Fix: font folders scan 5000 entries / cumulative 4 GiB with 128-font / 64 MiB bounded background batches.
Fix: asynchronously refresh FontDb instead of UI-blocking text.rescanFonts.
Keep approved keyboard shortcuts, D/C/S, SAF, updater and startup updater.
Only separate com.artcraft.vectorcraft.test package; no original permanent signing key, no GitHub Release.
Run preflight unit + JVM tests; compile and upload disposable signed ARM64 APK if all gates pass.
