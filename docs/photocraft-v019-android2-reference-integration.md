# PhotoCraft v0.19.0-android.2 compatibility scope
Source reference: morte2437/photocraft-android, tag android-v0.17.0-4 (MIT/Apache-2.0). The ArtCraft app uses **NativeActivity**; the reference uses **GameActivity**. Do not swap activities, modify published v0.14.0-android.4 files, or change signing keys.
## Implemented in disposable-runner compatibility overlay
- ArtCraft-owned show/hide, left/right Shortcut Pad menu with persisted settings and initial one-shot action keys. Not the full rotary wheel/hold-modifier router of the reference.
- In-app Help > Check for Updates routed to an Android-native updater adapted from the reference, with ArtCraft-owned PhotoCraft release tags and in-app download/installer prompt; installs require matching Android signing identity. Test APK uses disposable key, so **do not expect it to update a production-signed installed app**.
- Existing egui trackpad wheel emulation for two-finger scrolling on menus/panels.
- Full official PhotoCraft v0.19.0 engine, existing GPU compositor setup, SAF, AI shell and stable Android input retained.
## Still requiring functional engineering and device QA
- Real pen tilt/pressure/eraser + hover JNI through NativeActivity; no claim of fully working pen just from fork README.
- Canvas pinch/pan/twist, palm rejection with stylus proximity, reorderable touch lists, inertial scrolling and full Shortcut Pad spin-wheel/held modifiers.
- Restore native font import, check/update feedback, AI token clipboard paste, ESC text editing, V/T tool shortcuts and Y/N/C dialog keys; the owner reported regressions in prior build.
- Ensure top-left UI Pc logo matches launcher Pc icon; validate PNG extracted from the APK.
- Test updater on a **same-signer** candidate before ever enabling a stable-channel auto-install. No automatic merge/release.
