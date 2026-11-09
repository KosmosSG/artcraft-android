# VectorCraft v0.21.0-android.24 — failure-only investigation

Baseline: Android.23 commit 9adb6a6e474a9983c3147305db096b96a3c4bc71; run 42560861263.
Target: HONOR MagicPad 4 ARM64, disposable-signature test only.

## Device findings
- FAIL: repeated cold-start black screen / delayed launch.
- FAIL: menu trackpad scrolling versus smooth touchscreen / PhotoCraft.
- FAIL: two-finger trackpad pan and pinch; accidental selection.
- PASS (protected): V/T/H after typing, ESC; Ctrl+W and repeated D/S/C.

## Verified compile-log clues
- `AndroidMenuScrollSmoother.menu_scroll` field never read.
- `classify_android_precision_scroll` import/function unused.
These indicate dead or unconnected smoothing logic, NOT proof of the complete root cause.

## Review gates before any CI run
1. Instrument Activity onCreate, surface creation, Rust/native startup and first frame. Distinguish launch-theme gap, blocked UI thread and renderer delay. Use SplashScreen API / immediate launch window without disguising failed initialization.
2. Trace the Android trackpad input pipeline (SOURCE_MOUSE/TOUCHPAD, ACTION_SCROLL, axes, gesture scale) through winit/egui. Check that menu scroll smoothing is actually invoked, delta units and sign are correct, and scroll doesn't create selection.
3. Route two-finger trackpad pan/pinch through the same navigation commands as touch, but preserve separate device classification, focal point and gesture lifecycle. Verify no drawing or selection while navigation is active.
4. Preserve approved fonts, icons, adaptive cursor, GPU optimizations, update checker, keyboard shortcuts, D/S/C, ESC, stylus, touch behavior and all other Android customizations.
5. Run source/behavioral tests and review diff before **one** optimized ARM64 CI build. Avoid speculative reruns.
6. Verify separate test application ID, disposable signing, version, ARM64 libraries, APK checksum and private artifact. Never access production signing secrets.

## Release constraints
Do not alter published release, original signing keys, merge, tag or publish. Await HONOR MagicPad 4 device testing before any permanent release.
