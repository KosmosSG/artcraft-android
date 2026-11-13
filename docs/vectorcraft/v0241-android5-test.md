# VectorCraft v0.24.1-android.5 — verified in-app updater (TEST ONLY)

## Objective
Allow the production-signed VectorCraft package to check `KosmosSG/artcraft-android` releases, download a published **VectorCraft ARM64 APK within the app**, verify the exact published GitHub asset digest and installed package identity/signature, then request **Android system installation approval**. Existing separate, ephemeral-signed test APKs must never overwrite a production VectorCraft installation.

### Implementation
- In **About → Updates**, preserve Stable-only / Stable + Preview choice and optional startup checks. Add "Download & Install VectorCraft <version>" only if a newer official APK with an exact expected filename, original release URL, size and GitHub SHA-256 digest is available.
- User taps explicitly; there is no automatic download or install. Download over HTTPS to app-private cache, limited to 400 MiB, with byte-count bounds, redirect-host restriction and SHA-256 verification. No arbitrary URL is accepted from Rust UI.
- Verify that APK metadata reports the production package `com.artcraft.vectorcraft`, the exact release version, a strictly higher Android versionCode, identical current APK signing identity and ARM64 native library.
- Install through Android `PackageInstaller.Session`, requiring user confirmation. If "Install unknown apps" permission is disabled, open Android's per-app Settings screen and require the user to tap Download again.
- Production package installs only. The disposable test application ID `com.artcraft.vectorcraft.candidate_v0241a5` is explicitly ineligible; no build/test can install a production APK without the production certificate.
- The original stable release, signing material, upstream sources, file I/O and app data are untouched. No silent installations, signature bypass, automatic release publication or external file exposure.
- Installed updater callbacks are checked against a private random token; a forged Intent cannot authorize installation.

## Test plan — HONOR MagicPad 4
1. Install the Android.5 candidate alongside the published VectorCraft. Check About → Updates, Stable/Preview toggles, startup-update preference, check failures and open-release link. Confirm no download/installation is offered for the separately signed test app.
2. Ensure existing **Stylus Wheel compact dialog** with 84% wheel size / 78% opacity defaults, floating preview, eight slots, pen button, Ctrl+Z Undo and Ctrl+Shift+Z Redo remain intact.
3. Retest opening imported `.ai` and Type editing, including **Ctrl+Q → relaunch**. The persistent typing regression remains unresolved and is not claimed fixed here.
4. Production-sign/install the updater **only after explicit approval**, then use a *newer officially published* release to exercise the full download, SHA-256, identity, signature, permission and Android-install confirmation flow on a test device. Simulate bad digest, mismatched signer/package, bad version, network truncation and install cancellation in isolated tests before publishing.

**Stop at a disposable-key ARM64 test APK for owner verification.**
