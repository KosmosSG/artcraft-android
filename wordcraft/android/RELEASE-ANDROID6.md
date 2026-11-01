# WordCraft v0.9.0-android.6 — release preparation (NOT PUBLISHED)

## Device-tested candidate
- Branch: `feature/wordcraft-unsaved-dcs-20261029`
- Tested code commit: `061837c6923d161bffd1709072bbce4a37aa3e0c`
- Successful Actions build: https://github.com/KosmosSG/artcraft-android/actions/runs/41327248067
- Device-tested on HONOR MagicPad 4: D/C/S without tapping dialog, Ctrl+N, correct approved blue Wc icon, and Save/Don't Save/Cancel touchscreen.
- The build's temporary-key-signed APK is **not** a stable-release signing candidate. Rebuild from the exact tested commit for release; do not silently incorporate later changes.
- Proposed release tag: `wordcraft-v0.9.0-android.6`; proposed release APK: `WordCraft-v0.9.0-android.6-arm64-v8a.apk`.

## Permanent signing gate (blocking)
1. Locate the **original WordCraft signing key** and its matching certificate fingerprint for the installed, publicly released WordCraft android.4. Verify the certificate first; never assume the key exists or reuse a different application's key.
2. Prepare an unsigned/aligned production APK from the *exact tested source*, not from a temporary-key-signed artifact if rebuilding can be done cleanly.
3. If signing in Linux Lab, keep keystore and password offline. Use Android SDK `apksigner` and `zipalign` (align before signing); do not store keystore/password in this repo or upload them.
4. Verify ARM64-only, package `com.artcraft.wordcraft`, versionName `0.9.0-android.6`, versionCode `100000006`, adaptive icon assets, and that the resulting APK is signed by the **same** production certificate as the prior public release.
5. Record SHA-256 of signed APK, signing certificate and the exact source SHA. Test upgrade installation, launch, D/C/S repeated openings and Ctrl+N without loss of app data. Never instruct users to uninstall an existing signed app just to replace a signing identity.

## Publication gate (blocking)
- Review differences from the device-tested binary and confirm no further behavioral changes.
- Create a *draft* GitHub release with changelog and verified **permanently signed** APK only after gate above passes.
- Publish only after owner approves the final signed build. Keep android.4 intact until then.

## User-facing release note draft
WordCraft Android v0.9.0-android.6 improves keyboard and dialog behavior on Android tablets. The Save Changes dialog now takes keyboard focus automatically so D (Don't Save), C (Cancel), and S (Save) work without tapping the dialog first. Ctrl+N creates a new document. The approved blue Wc launcher icon is restored; Save/Don't Save/Cancel touchscreen controls remain usable.
