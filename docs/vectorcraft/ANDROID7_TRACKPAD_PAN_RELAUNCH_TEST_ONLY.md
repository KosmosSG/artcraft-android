# VectorCraft v0.23.0-android.7 — MagicPad 4 Trackpad / Relaunch TEST ONLY

Draft stacked on Android.6 PR #155, Android.5 PR #154 and Android.4 PR #153. Preserve the accepted 9 Android.5 tests and Android.6 touchscreen gesture work. Test package must remain **com.artcraft.vectorcraft.test** ARM64 with a disposable signing certificate, never production keys.

## Device-reported Android.6 issues (2026-11-10)

1. Physical **trackpad**, two fingers on **canvas**: finger swipe UP should move artwork UP; DOWN moves artwork DOWN.
2. Trackpad canvas: swipe LEFT should move artwork LEFT; RIGHT moves artwork RIGHT.
3. Two-finger trackpad scrolling feels slightly slow/hard to recognize, but **pinch-to-zoom is perfect** — do not regress pinch.
4. Ctrl+Q then reopen intermittently shows Android "Not Responding" for seconds, then recovers. The popup is NOT reliably fixed merely because startup completed.

## Android.7 bounded changes

- Canvas-only reversal of both x/y precision trackpad wheel deltas *before* egui smooth-scroll integrates. Menu-only natural direction from Android.5 remains unchanged. No synthetic selection, wheel replay or new inertia loop.
- 1.15x bounded point-wheel response gain on the canvas. Backend recognizes genuine source=touchpad two-pointer and relative axis packets sooner even before OEM classifies them as Swipe; backend geometry-only initial pan threshold 7.0 -> 4.0 screen px with stronger movement-vs-spread separation. All native pinch axes, scaling and thresholds remain unchanged.
- Remove redundant 48ms-repeating Java SurfaceView/PixelCopy probe on startup, after previous Android.4 diagnostic showed repeated buffer-probe timeout with no sampled pixels. Use the previously accepted direct splash removal after first native UI traversal. This is a plausible ANR-related performance mitigation, **NOT a proven ANR fix**.
- Lightweight no-user-data main-looper scheduling delay sampling during startup through onDestroy; Diagnostic Session adds main_looper_max_delay_ms / main_looper_max_delay_stage. An actual Android ANR trace remains preferable to infer the root cause.
- Full source guards and Rust test gates before expensive ARM64 compilation. No changes to Android.5 first pinch, Android.6 touchscreen two-finger reverse scroll, keyboard/IME/D/S/C, fonts, updater, adaptive cursor, native-loop-first quit or GPU renderer.

## Acceptance — HONOR MagicPad 4

- Trackpad two-finger canvas swipe UP/DOWN/LEFT/RIGHT: actual artwork follows fingers in all directions; starts promptly with short glides.
- Trackpad pinch immediately before scrolling, after finger lift, after two-finger scroll: all PASS; no unwanted selection.
- Popup trackpad swipe up reveals later menu items; swipe down earlier items.
- Touchscreen two-finger vertical canvas scroll direction as Android.6, horizontal scroll, responsive detection and pinch; one-finger object selection; stylus.
- Type tool V/T/H/ESC after typing; Ctrl+W -> D/S/C repeated; fonts, updater and 5 cold starts.
- Ctrl+Q->reopen **10 times** without data clearing; report number and duration of any Not Responding warnings. If one occurs, select Wait, then Diagnostic Session > Refresh Snapshot > Copy Report; include main_looper_max_delay_ms/stage and prior_process_stage. If available, capture Android ANR main-thread traces.

Strict STOP: no merge, permanent signing, tags, GitHub Release or publishing.
