# FilmCraft v0.19.0 Android — Fc Menu + In-App Updater Test

## Reported device issue (HONOR MagicPad 4, 10 November 2026)
- Existing isolated `com.artcraft.filmcraft.test` candidate shows a flat Fc popup, unlike the grouped GridCraft app menu.
- `Check for Updates` reports `Update comparison requires an official Android versionName` when installed version is `0.19.0-android.1-test`.
- Published `filmcraft-v0.17.0-android.1` APK is named `FilmCraft-v0.17.0-android.1-arm64-v8a.apk`, not the original updater's assumed `filmcraft-0.17.0-android.1.apk`.

## Changes isolated to v0.19 source overlay
- `tools/filmcraft/header_patch_v019.py`: compact Fc icon popup follows GridCraft's grouped controls. Top-level fonts, Font Catalog & Diagnostics submenu, App Updates submenu, Appearance submenu (opens native preferences), Keyboard Shortcuts, About FilmCraft, Home. Trackpad hover and production branding preserved.
- `tools/filmcraft/FilmCraftActivity.features.v019.java.inc`: official GitHub release metadata, validated source URLs, proper release asset names, SHA256SUMS verification, bounded Android DownloadManager transfer into the app's own download directory, APK identity and production signing-certificate continuity checks, then Android's user-confirmed installer.
- `tools/filmcraft/filmcraft_features_v019.rs`: adds download/install JNI commands and progress/error reporting, preserving fonts, existing shortcuts and state.
- `tools/filmcraft/runtime_patch_v019.py`: scopes downloader's installer permission to generated FilmCraft Android launcher.
- `tools/filmcraft/verify_android_features_apk_v019.py` and `test_upstream_v019_update_contract.py`: checks compiled JNI methods and manifest permission as well as source-level guards.

## Test package safety
- Keep `com.artcraft.filmcraft.test` on disposable signing keys, not the production identity. It can check and download/verify an official stable APK for functional testing, but **does not launch the production APK installer**.
- The production build later uses `com.artcraft.filmcraft` and original signing certificate, never a new signer. It permits installation only if APK version increases, APK identity matches, SHA256SUMS verifies, and archive signer matches installed production.
- New ephemeral signing may require uninstalling a prior disposable test candidate before installing the new test APK; never uninstall the separately installed published FilmCraft.

## MagicPad 4 acceptance
1. Top-left Fc icon shows grouped menu with App Updates, Appearance, keyboard shortcuts, About, fonts and diagnostics. Trackpad pointer hover highlights rows and submenus, touchscreen selection works.
2. App Updates > Check for Updates shows a test-build safety notice rather than a versionName error.
3. App Updates > Download Verified APK verifies SHA256SUMS and APK identity; the test flavor must refuse installation over published FilmCraft.
4. In a future owner-approved production-signed build, App Updates > Download/Install must show Android's normal install confirmation and signing-continuity guard, never silent installation.
5. Validate font import/shared scan, native dialogs, ESC/focus, Ctrl+W D/C/S, Ctrl+Q, media import/export, clip playback, scrub, timeline gestures, portrait/landscape, resume/relaunch and GPU fallback.
6. Check signed APK SHA, separate package ID, `arm64-v8a` only, compiled JNI handlers, unknown-app-install permission, original Fc icon and offline project recovery.

No production signing, merge or release publication is authorized by this test change.
