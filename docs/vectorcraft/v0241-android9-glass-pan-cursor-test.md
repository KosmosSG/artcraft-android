# VectorCraft v0.24.1-android.9 — glass two-finger pan cursor isolation

**Baseline:** published `vectorcraft-v0.24.1-android.9`, tag
`9beff78fd24b59e806f65424f9ee6443943d2901`, plus the independently
owner-tested (passing glass pan direction) candidate run `43676135324`,
commit `60fd9d797f9cf282db609fa5ddde8d73522cc319`.

**User confirmation, 15 Nov 2026:** two-finger touchscreen panning now moves
the artwork as intended. A black mouse-arrow cursor appears between the two
finger contacts while panning, shown in `SVID_20261115_132351_1.mp4`.

## Targeted fix

The Android winit input layer deliberately emits a *synthetic* midpoint
`CursorMoved` before the canvas `MouseWheel PixelDelta`. The pointer event
is necessary for canvas wheel targeting, so do NOT remove or reverse it.
Keep the approved native glass source tag and +1.15 canvas pan gain,
and do NOT change trackpad (-1.15), menu, pinch, stylus, IME or .ai import.

Instead, mark the real native glass pan at the Android egui input hook and
suppress the native/painted cursor in the canvas while that synthetic source is
active. Do not send selection/tool hover behind the two-finger cursor. A real
mouse/trackpad/stylus `PointerMoved` without an active glass pan clears
the cursor-suppression marker. No user coordinates or document content are
persisted.

The distinct temporary test launcher is **VectorCraft Pan Cursor Test**,
installed alongside previous test candidates, not over the published app.

## HONOR MagicPad 4 test checklist

1. Open a new blank document; swipe two fingers up/down/left/right. The art
   moves with your fingers; the black arrow no longer appears.
2. Lift both fingers: the synthetic cursor should not linger.
3. Hover the HONOR Magic-Pencil 4s: its usual hover pointer must reappear.
4. Move the trackpad pointer and pan with two trackpad fingers: both functions
   should remain unchanged.
5. Use pinch zoom on glass and trackpad and scroll through menus and the
   stylus wheel customization dropdown.
6. Try ordinary single-finger selection and stylus wheel activation.

The build passes source and generated-code checks only. The actual cursor
fix is not confirmed until the user tests it. This test does not attempt to
repair the separate .ai opening / text typing regression.

No production signing, merge, publishing or release replacement.
