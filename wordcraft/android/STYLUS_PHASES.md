# WordCraft Android stylus development

Protected production baseline: `wordcraft-v0.15.2-android.3`. Isolated
candidate branch: `feature/wordcraft-v0152-android4-stylus-20261107`. Production package, keystore, prior
stable releases, installed documents and saved settings must remain untouched.

## Phase 1: pen input integration (source staged; device tests pending)
- Distinguish Android `TOOL_TYPE_STYLUS` / `TOOL_TYPE_ERASER` from fingers.
- Preserve upstream WordCraft's Draw ink engine, document save, pen/eraser,
  lasso, undo, Ink to Shape and document selection. Do not replace it.
- Track hover, contact and pressure safely; report live pen state only inside
  the existing Wc icon menu, never as a floating screen overlay.
- Reject accidental new finger gestures while a stylus is in contact, but
  forward stylus events to the upstream editor and keep ordinary two-finger
  touchscreen/trackpad scrolling when no stylus is touching.
- Test pen drawing, erasing, page navigation, stylus hover, physical keyboard,
  Gboard typing, Ctrl+W/D/C/S, Ctrl+Q, Ctrl+Shift+S, font importing,
  updater, and document save/reopen on HONOR MagicPad 4.
- Pressure is currently telemetry only; pressure-dependent ink stroke width
  requires upstream ink-schema changes, and must not be claimed as implemented.

## Phase 2: handwriting -> editable WordCraft text (NOT implemented yet)
- Add a separate user-selectable Write to Text tool/mode, not a replacement
  for the existing Draw tab or Android keyboard.
- Evaluate Android 14+ platform stylus-handwriting IME in the existing
  EditText/InputConnection bridge. It may depend on OS/IME support.
- For reproducible offline recognition, evaluate Google ML Kit Digital Ink
  Recognition v19.0.0, requiring explicit first-use model download and
  consent. Never send handwritten data to a remote API by default.
- Capture stroke sequences with coordinates and timestamps, bound memory,
  cancel recognition on document close, and avoid duplicate insertion.
- Present recognized candidates for correction/acceptance; insert through
  existing WordCraft text-input actions, retaining undo, selection and save.
- Preserve original ink unless the user explicitly accepts conversion.
- Regression-test layout, save/reopen, IME focus/keyboard shortcuts,
  pen/finger separation, multi-touch, idle CPU, and offline recognizer model.
- Use an isolated, disposable-signed ARM64 candidate, not a production key.

## Release gates
No automatic permanent signing or publication of stylus candidate. Do not
claim either feature passed real-device tests until user explicitly confirms.
