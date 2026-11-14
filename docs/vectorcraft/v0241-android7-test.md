# VectorCraft v0.24.1-android.7 — separate-install ARM64 candidate (TEST ONLY)

Base: exact Android.6 successful source commit 8a5f929f92f37c2ce75a42dbbc1c00deb451be1a.

## Candidate changes
- Physical, printable, unmodified KeyEvent while the native editor has requested IME focus now commits via the existing ordered Android IME event queue and wakes the native event loop. Modifier shortcuts remain delegated to existing winit/egui handling.
- Preserve prior Android.6 PhotoCraft-style wheel UI and existing Android.5 in-app verified download/installer path.
- This change **does not establish a permanent fix** until tested against the real imported Crafticon V2.ai and multiple relaunches. No on-device tests are possible in CI.
- PhotoCraft-style App Updates visual parity remains a separate review item; existing Android.5 verified updater logic is retained unchanged by this candidate.

## Required HONOR MagicPad 4 device matrix
1. New blank document: Type tool, physical keyboard, editing and persisting text.
2. Import Crafticon V2.ai: edit existing live text, add text; compare missing-font/live-text geometry, protected and converted paths.
3. Ctrl+Q then relaunch 10 times; test both new document and imported .ai each time.
4. Force-stop/restart without clearing data; ensure no regression.
5. Ctrl+Z/redo, V/T/H, ESC, Ctrl+W D/S/C, stylus hover/button/wheel, trackpad scroll/zoom.
6. Vc menu > App Updates: check release; no update, available update, HTTP failure, checksum mismatch; verify bottom-center notification and PhotoCraft workflow in a subsequent UI parity patch.
7. Never install a test-signed .candidate APK over a production signed package.

No merge, permanent signing, publication, tags or modification of existing releases.