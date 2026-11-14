# VectorCraft v0.24.1-android.7 — physical typing recovery and PhotoCraft-style updates (ARM64 TEST ONLY)

## Pinned, protected inputs

- Android.6 test source: `8a5f929f92f37c2ce75a42dbbc1c00deb451be1a`
- Official upstream v0.24.1: `f4922aa7ac99a4f6d56fc68a83a44945207ec610`
- Reference Android builder: `52308fbcb26d8d8625f35fc1f048813f8e1e12a8`
- Android.7 changes isolated on `fix/vectorcraft-v0241-android7-typing-updates-20261114`; no merge, release, or production key.

## Candidate changes

1. MagicOS physical printable-key events are forwarded to the existing native Type sequence through a dedicated `h` text event only while the real Type editor is active. Java consumes these accepted key-down/up events so native winit cannot type them a second time. Soft IME commits/preedit, real IME reset completion, Ctrl+Q/W/Z, navigation and the upstream text editor remain authoritative. No user text or document contents are written into diagnostics.
2. Existing Android.6 document-UID fencing, Java focus epochs, queued reset-completion acknowledgments, imported live-text hit testing, Ctrl+Q teardown and stylistic wheel features are retained.
3. Vc → App Updates retains the official VectorCraft release filter and existing opt-in verified in-app download. `Check for Updates` is nonblocking and no longer forcibly opens the About dialog. A non-interactive PhotoCraft-style bottom-center charcoal pill announces progress/results; the About → Updates tab still holds detailed results, release channel and explicit download actions.
4. `Check for updates at startup` displays an actual persisted checkmark in the Vc submenu and a brief pill on change. No automatic download or installation.
5. Candidate has a separate `com.artcraft.vectorcraft.candidate_v0241a7` application ID, ARM64 only, an ephemeral builder certificate and test-only artifact retention. APK verification must reject the production signer.

## HONOR MagicPad 4 device acceptance (pending)

1. New blank document: Type tool → click to create live text → type 30 characters, including lowercase, uppercase (Shift), numbers, punctuation, spaces and Backspace. Test the physical keyboard and on-screen IME separately, without duplicate letters.
2. Import `Crafticon V2.ai`: select a *live editable Text object* (not paths/outlines), click Type, insert text and edit existing text. Close document; create a new document; repeat.
3. Ctrl+Q → relaunch 10 times; confirm immediate typing in new and imported documents, including after leaving the editor with Escape and returning. Do **not** clear data as part of the test.
4. Confirm Ctrl+Z undo, Ctrl+Shift+Z redo, Ctrl+W → original D/S/C modal, V/T/P, soft-IME composition/deletion, and no dead-key duplication.
5. Confirm stylus hover/button, 8-slot PhotoCraft-style wheel, persisted wheel settings, canvas input isolation, menu dropdown scrolling, zoom/pan and adaptive cursor.
6. Vc → App Updates → Check for Updates: confirm bottom-center pill then result (including offline/error), no unsolicited About popup. Confirm checked startup preference survives Ctrl+Q relaunch; About → Updates still offers Stable/Preview choices.
7. Production APK installation is **not** possible from this disposable-signed package. Verify ARM64-only APK contents, distinct package name, signature, exact pinned version and SHA-256 before sharing.

## Important limits

A green CI build proves source gates, compilation, packaging and signature checks; it does **not** prove the MagicOS-specific typing failure is permanently corrected. Device acceptance above must pass before signing or publishing any release.
