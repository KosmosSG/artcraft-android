# VectorCraft v0.24.1-android.10 — native IME reset transport test

**Test only.** Based on published VectorCraft v0.24.1-android.9 source.
The original-signed app, stable package, published release/tag/APK,
user files, stylus wheel and in-app update system are NOT modified.

## Confirmed Android.9 packaging bug

A real HONOR MagicPad 4 diagnostic report showed:

- tool=type, editing=true, composing=false, field=false
- ime_commit_callbacks=42, raw_ime=129
- type_route=181, stale_ime_rejected=126
- reset_requested=51, reset_matched=0, Java ime_resets=0
- tool_text_calls=0, edit_accepted=0

The Android.9 CI workflow applied the app-source half of
tools/vectorcraft/patch_android8_ime_reset.py, but **did not run the required
--vendor half**. The pinned builder's winit backend therefore toggled
set_ime_allowed(false/true) instead of sending the request ID through
AndroidApp.vc_reset_ime -> JNI vcResetIme(requestId) -> Java IME queue
"r<serial>" -> Rust bridge matching -> ImeResetCompleted.

This Android.10 test enables the already-reviewed --vendor integration,
with a fail-closed preflight that demands all native, JNI, Java and Rust
handoff methods be present, and rejects the old toggle-only backend.

Keep IME stale rejection and exact request identity checks intact.
The fix remains a candidate until physical typing is verified on device.

## Device acceptance

1. Install the separate app test APK without removing the stable release.
2. Open Keyboard Diagnostics > Start / Reset.
3. Create a new document, activate Type, then type "TEST 123".
4. Open Crafticon V2.ai and type into editable text. Confirm text appears,
   persists after close/reopen, and neither duplicates nor vanishes.
5. Alternate Type and Selection, switch documents, press Ctrl+Q and relaunch,
   repeat at least 10 times.
6. If failure reappears: Stop, Copy Report. Compare Java ime_resets,
   Rust reset_requested and reset_matched, stale_ime_rejected,
   raw_ime, type_route, tool_text_calls, and edit_accepted.
7. Check Undo, Escape, Ctrl+W D/C/S, V/T/P, stylus wheel and hover,
   trackpad scrolling/pinch, 5,000-font shared import and in-app updater.

Only when device testing passes should the fix be described as verified.
No production signing, merging or publishing was authorized.
