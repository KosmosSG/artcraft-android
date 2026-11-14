# VectorCraft v0.24.1-android.9 — touchscreen canvas pan direction TEST

**Protected baseline:** published tag `vectorcraft-v0.24.1-android.9`
(commit `9beff78fd24b59e806f65424f9ee6443943d2901`).

This candidate **does not incorporate v0.24.1-android.10's JNI IME reset transport**
or make any new changes to the typing stack. The remaining typing issue is
acknowledged but explicitly out of scope.

## Only intentional functional change

Reverse the sign of both X and Y two-finger **touchscreen** canvas translation
as requested after HONOR MagicPad 4 screen-recording feedback:

| Gesture on touchscreen canvas | Expected artwork movement |
| --- | --- |
| Two fingers swipe up | Artwork moves up |
| Two fingers swipe down | Artwork moves down |
| Two fingers swipe left | Artwork moves left |
| Two fingers swipe right | Artwork moves right |

The path remains gated to two-finger canvas touch input. Preserve native
**trackpad scrolling**, **pinch zoom**, menus, single-finger editing, stylus
wheel, hover, updater, fonts, keyboard shortcuts and the Android.9 typing
behavior exactly as already released.

## Verification

This is a **separate-install, disposable-signed ARM64 TEST APK**. Do not use
the production signing key, merge, publish or overwrite the Android.9 tag,
APK or release. Source-level staging checks cannot substitute for device tests.

On HONOR MagicPad 4, open a document and swipe in all four directions with
two fingers on the empty canvas, then pan over selected artwork; verify the
canvas follows the intended direction without selecting artwork. Confirm
pinch zoom, trackpad two-axis scroll, stylus wheel and ordinary single-finger
editing still behave as before. **Do not evaluate this build as a typing fix.**
