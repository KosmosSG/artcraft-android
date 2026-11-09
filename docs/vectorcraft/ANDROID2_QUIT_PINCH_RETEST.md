# VectorCraft v0.23.0-android.2 — focused Ctrl+Q ANR and pinch test

## Protected baseline
Android.1 disposable ARM64 test looked good on HONOR MagicPad 4. Canvas two-finger scrolling and popup menu trackpad scrolling work. Type-tool typing recovered. New device findings: intermittent Android "VectorCraft Test isn't responding" after Ctrl+Q; pinch zoom works but is often misread as two-finger scrolling. Preserve all other features and Android.1 test APK as fallback.

## Changes
1. Preserve upstream Save Changes D/S/C and app.quit gate. Once confirmed UI status is "quit", use a one-shot flag and egui ViewportCommand::Close, instead of calling finishAndRemoveTask() while inside eframe App UI. AFTER eframe::run_native() returns, ask Java to finish the Android task. Retain on_exit persistence, never force-stop or bypass Cancel. Emit lifecycle stage markers VC_QUIT_ANDROID2 native_close_requested/native_loop_returned/java_finish_posted; these are diagnostics, not proof of root cause.
2. Keep Android API 34 native touchpad scroll axes 50/51, pinch axis 52. Accept strong scale changes EVEN when the device classifies the packet as a swipe; accept consecutive same-direction small changes. For two-pointer fallback, recognize slight deliberate pinches and switch from scrolling only when spread change clearly dominates midpoint travel. Never apply both pan and zoom in the same packet or forward two fingers as canvas selection events.
3. Add isolated Rust math tests for small pinch, deliberate pan-to-pinch transition and scrolling with finger drift. Source preflight must verify code anchors before expensive ARM64 compilation.

## HONOR MagicPad 4 checks
- Ctrl+Q from Welcome, new blank file, edited unsaved file. Repeat quit-and-reopen 10 times without force-stop or clearing data; verify Ctrl+W D/S/C and Cancel never closes.
- Two-finger trackpad canvas scroll horizontally and vertically; slow/fast pinch in/out. No selection box, smooth panning and prompt zoom detection.
- Popup trackpad scrolling versus touchscreen, touchscreen gestures and stylus still work.
- Type tool Gboard/hardware typing, V/T/H and ESC, fonts/updater, five cold launches.
- If quit ANR recurs, Android bug report/logcat should include VC_QUIT_ANDROID2 stages. If pinch is still difficult, Vc > Keyboard Diagnostics > Diagnostic Session > Copy Report includes native axis/fallback counters and p50/p95 UI frame intervals.

## Safety
Version v0.23.0-android.2; separate com.artcraft.vectorcraft.test, ARM64 and disposable signing only. Android.2 temporary certificate may differ from Android.1; uninstall TEST package only if installation fails, after backing up test data. No merge, permanent signing, tag or publishing without device approval.
