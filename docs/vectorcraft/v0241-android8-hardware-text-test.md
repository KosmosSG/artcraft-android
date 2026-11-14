# VectorCraft v0.24.1-android.8 — disposable ARM64 keyboard-route candidate

Test-only package: com.artcraft.vectorcraft.candidate_v0241a8
Production VectorCraft, original signing identity and all published releases are unchanged.

## Why this candidate differs from Android.7

The prior physical hardware key handler encoded normal printable keys as
"c" events, i.e. egui::ImeEvent::Commit. Pinned upstream rejects such IME
terminals while its composition route is Stale. This candidate encodes only
unmodified physical printable keys as "t" and reconstructs egui::Event::Text.
Software InputConnection composition and commits remain on the original "p"/"c"
path, with their ordered reset IDs and generation guards unchanged.

A plain physical Android key carries authoritative no-Ctrl state; the Rust
modifier tracker now honors a matching ModifiersChanged(NONE) before that
specific text event to recover if Ctrl-up was lost during Ctrl+Q / Activity exit.

## Verification on HONOR MagicPad 4 (must be done before calling fixed)

1. Install disposable test candidate without uninstalling stable VectorCraft.
2. Create a blank document, choose Type, click to create a text frame, then
   type "HELLO 123 !?" on physical keyboard. Confirm visible characters.
3. Edit existing text from Crafticon V2.ai using the same physical keyboard;
   confirm no character disappears and no duplicate characters are inserted.
4. Close the .ai file and create another document; test physical typing.
5. Ctrl+Q, relaunch, open the .ai and type again. Repeat at least 10 times.
6. Check Ctrl+Z, Ctrl+W -> D/C/S, Escape, V/T/P, stylus wheel Pencil button,
   hover, trackpad gestures, imported fonts, and in-app updater.
7. If typing still fails, use the built-in Keyboard Diagnostics Copy Report and
   share the aggregate counters, especially activity_physical_down,
   physical_text_queued, raw_text, raw_ime, type_route, tool_text_calls,
   edit_generated, edit_accepted, edit_rejected, stale_ime_rejected and
   reset_matched. The report contains no typed content and should be
   redacted for any other private information before sharing.

## Diagnosis from counters

- activity_physical_down unchanged: physical keys never reached Activity dispatch.
- activity_physical_down rises, physical_text_queued unchanged: hidden EditText
  did not receive/accept printable keyboard keys (or not in editing mode).
- physical_text_queued rises, raw_text unchanged: Java-to-Rust polling dropped it.
- raw_text rises, type_route unchanged: Type tool focus/route did not take text.
- type_route and tool_text_calls rise, edit_accepted unchanged: inspect engine
  preview and text-edit target, not the keyboard.
- stale_ime_rejected rises: true IME commit path remains guarded; inspect
  request completion and context identity rather than disabling the fence.

These are conditional diagnoses, not proof that any particular route is broken.
No user document contents or keystrokes are intentionally logged.
