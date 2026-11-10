# VectorCraft v0.23.0-android.6 — touchscreen canvas two-finger natural scroll

TEST ONLY — standalone `com.artcraft.vectorcraft.test` ARM64 disposable-signed APK.
Stacked on v0.23.0-android.5 (draft PR #154; prior PR #153).

## Device evidence
Android.5 HONOR MagicPad 4 PASS 9/10: first pinch, lift+pinch, scroll+pinch, natural menu scrolling, no-selection two-finger canvas/menu scrolling, touchscreen two-finger scroll/pinch, keyboard Type/V/T/H/ESC, Ctrl+W/D/S/C, five cold starts/fonts/updater.
FAIL 1/10: occasional Android ANR warning when reopening after Ctrl+Q. **Do not claim this fixed.** Existing quit path and VC_QUIT4 stage instrumentation are unchanged.

## Scoped modification
- Vertical **touchscreen canvas** two-finger scroll now uses reverse direction requested by tester: two-finger swipe UP scrolls view DOWN to later canvas content; swipe DOWN scrolls view UP.
- Retain native touchscreen pinch (zoom), horizontal translation and popup/trackpad gesture behavior.
- If egui multi_touch() is not ready, track raw egui Touch start/move/end events for exactly two contacts that began on the canvas, and use their midpoint motion immediately with no artificial slop threshold. Stop on either lift, cancel, popup or dialog. Disable this fallback once egui multi_touch() is available to avoid double movement.
- Keep Android.5 hoverless trackpad pinch centered fallback separate; never select/draw with two-finger touch scrolling.
- All generated-source anchors guarded in preflight, before NDK/ARM64 compilation. Strict pinned Storytold upstream and Mostafa builder.

## HONOR MagicPad 4 acceptance
- Touchscreen two-finger swipe UP => canvas scroll DOWN, swipe DOWN => canvas scroll UP. Check first movement registers without holding both fingers.
- Touchscreen two-finger pinch without accidental selection, one-finger object selection, pen/stylus unaffected.
- Native trackpad pinch immediately before any scroll, after lifting, after scrolling. Natural trackpad menu vertical list scroll.
- Canvas/menu scroll no selection; Type/V/T/H/ESC; Ctrl+W D/S/C repeatedly; five cold starts/fonts/updater.
- Ctrl+Q→reopen ten times, note ANR warnings and copy Diagnostic Session + Android ANR trace if possible. This remains investigation.
- No permanent signing, merge, tag or publish.

STOP before merging or publishing.
