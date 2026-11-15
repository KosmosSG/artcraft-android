# VectorCraft v0.24.1-android.9 — native glass touchscreen pan test

**Baseline:** published `vectorcraft-v0.24.1-android.9`, commit
`9beff78fd24b59e806f65424f9ee6443943d2901`. This is a
temporary-signature, **separate-install** ARM64 APK, not a release.

## Why the earlier canvas sign patch showed no difference

The pinned Android winit implementation recognises a two-finger gesture on
the glass and sends `WindowEvent::MouseWheel { PixelDelta }`. At two contacts
it *suppresses* individual `Touch` events. The canvas's
`egui::InputState::multi_touch()` therefore has no translation to reverse.
Static canvas-source tests passed but did not exercise the active device path.

## Correction

- Keep the published Android.9 touchscreen, stylus and keyboard/IME behavior.
- Count native **glass** `GestureStep::Pan` packets (no coordinates, private
  content or identifiers), exposed to the Android canvas input hook.
- At the canvas only, distinguish glass wheel packets from the existing
  HONOR trackpad wheel stream. Reverse the previously shared negative wheel
  sign **only for the glass stream** on both axes.
- Leave the approved trackpad mapping, popup/menu scrolling, pinch zoom and
  stylus wheel alone. The native event delta itself is unchanged.
- Ignore Android.10 typing reset transport entirely.

## On-device checklist

Install the app labelled **VectorCraft Glass Test**. It is intentionally
separate from production VectorCraft and previous `VectorCraft Test` builds.
Open a document and test two-finger swipe up/down/left/right directly on
the canvas. The artwork should follow the finger direction. Also test
trackpad pans, trackpad pinch, glass pinch, single-finger selection and
touch scrolling in long menus, including the stylus wheel configuration.
For a repeatable diagnosis if the movement is still unchanged, copy the
existing VectorCraft Diagnostic Session after several canvas swipes and check
`vc_native_glass_twofinger_pan_packets` and
`vc_canvas_glass_remap_events`. Both are aggregate counts; no coordinates
or document data are collected.

The presence of the source tag and passing build gates does NOT prove
the HONOR MagicPad 4 behavior until you confirm it.

Do not permanently sign, publish, merge, modify protected Android.9
release assets, or assert that text editing was repaired.
