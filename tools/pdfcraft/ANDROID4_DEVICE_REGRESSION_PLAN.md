# PDFCraft v0.19.0-android.4 — device regression work plan

Branch based on draft PR #128 Android.3 head. TEST ONLY. Do not merge, publish, permanently sign, or touch production keys.

## Observed on HONOR MagicPad 4
- FAIL P0: Open PDF, Ctrl+Q, relaunch without clearing app data. Android.3 fails despite green CI.
- FAIL P1: Physical trackpad two-finger scroll activates sidebar tools / does not scroll PDF correctly.
- P2: Stylus pressure and drawing work, but ink visibly lags slightly behind tip.

## P0 lifecycle investigation
Capture logcat filtered for ActivityTaskManager, AndroidRuntime, PDFCraftLifecycle, NativeActivity, Rust panic and JNI during open > Ctrl+Q > relaunch. Compare launcher cold start, onNewIntent, onDestroy and process PID. Verify that the Java-side stale native loop flag is reset on new Activity and that finishAndRemoveTask is invoked on the UI thread before native teardown. Avoid process exit and clearing data. Add deterministic tests for all state transitions and 10 device relaunch cycles.

## P1 input routing
Instrument MotionEvent source, tool type, action, axis values, pointer count and resulting egui event. Distinguish SOURCE_MOUSE trackpad AXIS_VSCROLL/HSCROLL from pointer drag; convert trackpad scroll to Scroll without emitting pointer press/drag. Ensure gestures over canvas do not activate left toolbar; preserve intentional single-pointer clicks and touch gestures. Verify vertical/horizontal scroll and sidebar safety on hardware.

## P2 ink latency
Timestamp stylus ACTION_DOWN/MOVE samples through native dispatch, paint scheduling and frame presentation. Render an immediate preview of in-progress strokes, batch historical/coalesced samples, invalidate dirty regions where supported, and avoid synchronous save/recognition in pointer-move hot path. Preserve pressure width, hover and palm rejection. Do not introduce synthetic pressure or smoothing that creates visible lag.

## Protected regressions
Keep all six Android.3 PASS checks: unsaved S/D/C, HONOR Files PDF intent, persistent Light/Dark, imported/shared fonts, updater, stylus pressure. Preserve launcher/icon and current Android customizations.

## Candidate delivery gates
- Separate installable ARM64 package, version 0.19.0-android.4, disposable key only.
- Pre-build unit/generator checks; one combined build to conserve Actions minutes.
- Verify APK identity, ABI, disposable signature, upload artifact, provide test checklist.
- Device acceptance: Ctrl+Q relaunch 10/10; no accidental sidebar selection with trackpad; ink appears with lower latency and no dropped samples.
- STOP before permanent signing, merging or publishing.
