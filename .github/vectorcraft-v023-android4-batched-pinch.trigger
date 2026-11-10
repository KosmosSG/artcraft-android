VectorCraft v0.23.0-android.4 HISTORICAL AXIS PINCH + CTRL+Q STAGE REPORT TEST ONLY
Source pinned Storytold VectorCraft v0.23.0 5d0e892e2419f63bc0ea3c743ddff2e81e15fd3a
Builder pinned MostafaXS1 52308fbcb26d8d8625f35fc1f048813f8e1e12a8
Baseline: user's previously tested Android.3, protected keyboard/menu/fonts/updater
Fix: consume batched native AXIS_GESTURE_SCROLL_50/51 and PINCH_52 in single-pointer motion streams
Instrumentation: classified pinch/swipe and historical native axis counters per Diagnostic Session
Ctrl+Q: preserve native-first app quit, add VC_QUIT4 persisted stage ONLY (not a proven fix)
VersionName v0.23.0-android.4 VersionCode 16783904
APK com.artcraft.vectorcraft.test ARM64 disposable key, no production secret
One-shot CI, no permanent signing, merge, tag, release or publication

Retry once after early guard failure: Android.13/14 generated Activity already uses finish(), not finishAndRemoveTask(); corrected fail-closed patch anchor. No ARM64 compilation occurred in first run.

Preflight retry after correcting Python-only // comment syntax. Prior two runs stopped before SDK/NDK/ARM64 compile; exact privacy-safe Java/Rust quit-stage patch retained.
