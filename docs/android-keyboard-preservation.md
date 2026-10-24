# ArtCraft Android keyboard preservation contract

Scope: PhotoCraft, VectorCraft, and future app-specific Android keyboard integrations.
This document is a **release gate**, not a statement that untested tablet behavior is working.

## Protected functionality

1. Preserve the installed application's exact package name and permanent production signer; never substitute a test APK signer or uninstall to update. Check monotonically increasing versionCode against the installed build.
2. Preserve Android app-private settings on in-place APK updates. In VectorCraft, `persist_load` restores `ui.json`, `persist_save` writes the UI state, and separate files store touch-dock and startup-update preferences. Do not clear, replace, or silently reset these on an upstream merge.
3. Preserve user-customized **upstream** shortcut assignments and presets when they are represented in saved UI state; test save → restart → upgrade → reload with actual customized mappings before claiming this guarantee on-device. Avoid destructive preference migrations.
4. Preserve hardware left/right Ctrl, Shift, Alt tracking, event-ordered `ModifiersChanged`, focus loss reset, command-chord text filtering, and unmodified IME composition including non-Latin input.
5. Keep native touch shortcut dock, its current commands and text-editor protections, SAF file/font workflows, GPU diagnostics, in-app updates, launcher/in-app approved branding, Android IME support and keyboard menu access.
6. Keep official upstream shortcut semantics; **do not** override user custom bindings with new Android-specific defaults or intercept text input to create artificial tool commands.

## Upstream upgrade/release gate

- Start each upstream update from the application's last reviewed and released Android adapter, not an out-of-date `main` snapshot.
- Keep the enhancement in the app-owned Android wrapper or shared support code, not an untracked edit to a temporary upstream checkout. When the upstream keyboard API changes, port deliberately with reviewed tests.
- Run `tools/vectorcraft/test_android_keyboard_preservation.py` and embedded Rust modifier unit tests where host compilation permits. Run ARM64 `cargo check` on the exact pinned official source before candidate packaging.
- Confirm package/version/signature/ABI, release provenance, font/custom keyboard settings persistence, and upgrade-in-place. Back up tablet projects before installing test updates.
- Test actual Bluetooth/USB-C keyboard behavior on HONOR MagicPad 4: left/right mixed Ctrl/Alt/Shift holds; Ctrl+Z, Ctrl+S, Shift chord; key repeat; focus loss; text-edit suppression; IME Chinese input; dock; system-reserved shortcuts.
- Apply feature parity to PhotoCraft, VectorCraft and subsequently other ArtCraft apps separately. Do not auto-merge incompatible upstream changes or enable automatic upstream sync.
- No public APK release until approved build, original production signer, upgrade compatibility and device checks have passed.

### Current status

- PhotoCraft v0.14 uses `adapters/photocraft/src/android_modifiers.rs` for independent physical modifier tracking and carries its preexisting shortcut UI.
- This VectorCraft development branch ports the modifier safety logic to a dedicated `adapters/vectorcraft/src/android_modifiers.rs` without changing existing user shortcut bindings or menus.
- The separate GitHub Actions workflow uses **read-only** permissions and compiles without signing or publishing. Green source/compile gates alone are **not** proof of on-device compatibility.
