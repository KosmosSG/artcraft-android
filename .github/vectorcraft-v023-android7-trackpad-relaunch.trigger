VectorCraft v0.23.0-android.7 ONE-TIME DISPOSABLE ARM64 TEST APK ONLY
Branch fix/vectorcraft-v023-android7-trackpad-pan-fast-relaunch-20261110
Stacked draft PR #156 on #155 on #154 on #153
Native pinch scaling unchanged; protect all passing features
Trackpad canvas natural X/Y pan, earlier geometry pan, startup ANR mitigation/diagnosis
Fail-closed source preflight and behavior tests before ARM64 Rust compilation
DO NOT merge, permanently sign, tag or publish
Trigger 2026-11-10

Retry #2 source-only preflight: corrected misplaced canvas guard, no prior native compilation, preserve all scoped Android.7 behavior.

Retry #3: sync final preflight assertion to deliberate Android.7 direct-splash startup mitigation. Previous retry source-only, no native build.
