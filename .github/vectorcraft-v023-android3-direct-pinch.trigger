VectorCraft v0.23.0-android.3 DIRECT PINCH WITHOUT PRIOR SCROLL - TEMP ARM64 TEST ONLY
User result: Android.2 requires two-finger scroll before reliable pinch; diagnostic counters cumulative (native pan 33, native pinch 78, fallback pan 826, fallback pinch 1133, no-data 28).
Branch fix/vectorcraft-v023-android3-pinch-recognition-20261110; draft PR #152.
Pinch detector: initial threshold 3.5px, pan 7px, local two consecutive spread-dominant packets allow pan->pinch handoff even after long scroll.
Native API34 axes 50/51/52 preserved; no touchscreen/stylus/selection/menu/IME/keyboard change.
Diagnostic Start/Reset clears native counters; real newline separators in report; report header Android.3.
Keep Android.2 native-loop-first Ctrl+Q shutdown; unverified on device.
Version 0.23.0-android.3, versionCode 16783903, com.artcraft.vectorcraft.test ARM64, disposable key.
No merge, permanent signing, tags, releases or extra CI without new device evidence.
