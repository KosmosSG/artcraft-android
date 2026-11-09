VectorCraft Android.25 — RESTORE PUBLISHED REFERENCE TRACKPAD GESTURES (test only)

MagicPad 4 Android.24 tests (9 Nov 2026): FAIL cold start black 12+ seconds; FAIL menu trackpad scroll vs touchscreen; FAIL two-finger pan/pinch stutter; PASS V/T/H/ESC; PASS Ctrl+W D/S/C.

Reference verified: MostafaXS1/artcraft-android published release v0.5.0 (2026-11-05), VectorCraft 0.21.1, vendor/winit/src/platform_impl/android/mod.rs SHA 5b51799da50674fa85ae5e879ed71f00598aca9e; the pinned builder SHA 52308fbcb26d8d8625f35fc1f048813f8e1e12a8 ships that identical source. Our Android.23/.24 overlays added fallback and pan/zoom packet clamping. Restore EXACT published reference gesture section in final vendored winit, drop unused fallback state while preserving the rest of builder/owner Android keyboard, lifecycle, SAF, updater and stylus paths. Eliminate supplemental egui popup wheel attenuation, and log startup stages to diagnose the black delay without introducing another speculative cover timer.

All source alterations occur on disposable test branch only, no upstream auto-update. Build only after Python source guards + Rust gesture and IME regression checks. Pinned builder/upstream unchanged. Separate install com.artcraft.vectorcraft.test, VERSION_NAME 0.21.0-android.25, VERSION_CODE 16783385, ARM64, disposable test signing only. Never use original key, never publish, merge or tag. Only one Actions run after trigger. User will test cold start, trackpad menu vs touchscreen, 2-finger pan/pinch, shortcuts and save modal.

Preflight retry 2: Android.25 bootstrap instrumentation now anchors only NativeActivity super.onCreate, preserving the actual Android.23/24 startup-stage wrapper. Previous run 42605092130 failed before SDK install; do not reuse artifact or production keys.

Preflight retry 3: fixed duplicate Android.25 native hook guard; prior run 42605283754 passed native reference restoration and failed only on idempotence unit-test assertion, before Android SDK/NDK cost.
