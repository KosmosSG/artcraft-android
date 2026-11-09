# VectorCraft v0.23.0-android.1 — native trackpad prototype (TEST ONLY)

Baseline: draft PR #148, pinned Storytold v0.23.0, MostafaXS1 builder 52308fb, Android.25 working keyboard/IME, fonts, updater and startup overlays. Existing Android.26 was successfully built but HONOR MagicPad 4 trackpad pan/pinch stuttered. **The published MostafaXS1 v0.5.0 reference also does not offer working trackpad pinch/scroll on this device**; do not use it as a pass criterion.

## Isolated native implementation

- The final vendored winit Android backend is restored to the pinned reference, then receives the separate VectorCraft trackpad patch AFTER Android.25.
- Android API 34+ pointer axes `50` and `51` (per-sample two-finger scroll pixels) and `52` (per-sample pinch factor) take priority. The android-activity 0.6.1 enum recognizes these through `Axis::from(u32)`.
- Classified swipe and pinch are consumed exactly once. Even without a classification, direct axes are accepted for a touchpad. Two pointer-class pointers have a small, hysteretic pan/pinch fallback (unit tested), avoiding abrupt toggles or excessive clipping.
- No synthetic 165-Hz repaint loop, wheel attenuation, re-batching or inertia injection. Native velocity is left to Android/egui.
- Never convert trackpad gestures into touchscreen touches. Release the previous one-finger left-button state once at the start to prevent canvas selection boxes.
- The existing Diagnostic Session > Copy Report appends only five **aggregate native route counts**: API pan, API pinch, fallback pan, fallback pinch, and missing-data. No coordinates, filenames, keystrokes or document text are captured.
- No changes to touchscreen, stylus, physical keyboard, IME/Type, V/T/H/ESC, Ctrl+W/D/S/C, PDF/font/updater/branding, or published APKs.

## Device acceptance gate (HONOR MagicPad 4)

1. Five cold launches, no startup black screen.
2. Type tool: type letters using Gboard and hardware keyboard; ESC exits, V/T/H remain usable.
3. On canvas, trackpad 2-finger horizontal + vertical scroll and pinch zoom 15s each; no object/selection box, continuous motion. Record whether AXIS or FALLBACK counters rise.
4. Popup/menu trackpad wheel scroll compared against two-finger touchscreen; ensure neither direction reverses or jumps.
5. Touchscreen 2-finger pan and pinch, one-finger object selection, stylus, Ctrl+W → D/S/C, fonts, updater.
6. In Keyboard Diagnostics > Diagnostic Session, Start/Reset, reproduce gesture, Stop, Copy Report. Compare native route counts with UI-frame p50/p95; UI metrics are not actual Vulkan GPU presentation times.

## CI and release policy

The new workflow only fires when `.github/vectorcraft-v023-android1-native-pad.trigger` changes on the isolated branch, and uses a disposable APK signing key and separate package `com.artcraft.vectorcraft.test`. It runs a non-Android math Rust test and a source-overlay preflight before expensive ARM64 compilation. Never merge, permanently sign, tag or publish without device PASS confirmation.
