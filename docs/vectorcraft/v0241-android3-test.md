# VectorCraft v0.24.1-android.3 — ARM64 DISPOSABLE TEST CANDIDATE

**Status:** Source candidate, not user-verified. Separate app ID `com.artcraft.vectorcraft.candidate_v0241a3`, ephemeral signing; NEVER production-sign, merge, tag, or publish without explicit owner approval.

**Baseline:** v0.24.1-android.2 test branch `fix/vectorcraft-v0241-android2-wheel-relaunch-20261113` (commit `f10a635fedd266cb8cd93d6e53ba2014223b64d0`). Pinned official upstream v0.24.1.

## New Android.3 source changes

- **Hardware Ctrl+Z -> Undo:** call the *existing document* `edit.undo` command once per non-repeated Ctrl+Z key-down, even if native and Java fallback provide duplicates in the same input frame. Consume handled downs before upstream keyboard dispatcher to avoid undoing twice. Preserve untouched key releases and IME events.
- Only with an active document, outside dialogs or IME composition. Regular egui text fields own their keyboard undo. The VectorCraft Type editor may use document Undo if focused; no forced Escape or IME focus transfer.
- Ctrl+Shift+Z, plain Z, Alt+Z, key repeats, other shortcuts, wheel and native pen controls remain routed as before. Existing on-screen Shortcut Pad Undo and stylus-wheel Undo are unchanged.
- Thin orange circular wheel stroke matching Vc lettering, scoped orange size/opacity sliders, wider desktop/tablet customization controls. Preview and live overlay retain a shared painter. Existing hover capture/isolation tests retained.

## Device test: HONOR MagicPad 4

1. Create a blank document; draw two objects. Press **Ctrl+Z** twice: undo one committed document action per press. Hold Ctrl+Z and verify key-repeat packets don't cause unintended extra undo. Tap the Shortcut Pad Undo and the wheel Undo to compare.
2. Press **Ctrl+Shift+Z** and observe original Redo behavior. Plain Z while typing must enter text rather than undo. Normal inputs and Save Changes D/S/C dialogs must not lose focus or receive unintended undo.
3. Type text, exit Type with Escape, press Ctrl+Z. Then open an `.ai` document, edit text, press Ctrl+Z, close and create a new document, type again. **The existing imported .ai typing regression is NOT claimed fixed by this shortcut-only change.**
4. Use stylus button; verify center logo, thin orange outer stroke, orange slider thumb/track styling, live size/opacity preview, hover slot highlight and no selected objects behind the wheel.
5. Retest Ctrl+Q/relaunch 10x, W->Save/Don't Save/Cancel, startup responsiveness, keyboard V/T/H, two-finger pan direction, trackpad pinch, menu scroll and font import.

**Stop at an installable, verified temporary-signature ARM64 TEST artifact; no GitHub Release.**
