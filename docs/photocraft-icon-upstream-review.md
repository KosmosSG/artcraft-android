# PhotoCraft Android — guarded integration review

**Review-only; do not enable automatic builds or publishing.**

## Proposed next Android version
- Official upstream target: `storytold/photocraft` release `0.11.1`, only after verifying its tag and immutable commit.
- Proposed Android versionName: `0.11.1-android.1`.
- Proposed APK filename: `photocraft-0.11.1-android.1.apk`.
- Enforce Android `versionCode` strictly greater than the highest previously distributed APK; validate with `aapt` and an update-install test.
- The existing private signed workflow currently resolves plain numeric versions and must be adapted and tested before any release.

## Exact uploaded Pc icon
- Preserve the original user-uploaded cyan glass `Pc` PNG **byte-for-byte**. Do not redraw or approximate it.
- Stage at `assets/photocraft/launcher-pc.png` when original bytes can be committed.
- Builder supports `bash build.sh -photocraft -appicon=assets/photocraft/launcher-pc.png`.
- Inspect launcher icon generation, adaptive masking, and actual device appearance.
- **Icon not yet committed**. Do not enable the icon flag until the original file is present.

## Protect signing and enhancements
- Active signed workflow: private `KosmosSG/photocraft-signing-private/.github/workflows/build-photocraft-signed.yml`.
- Preserve signing backup, signing secrets, original certificate, `com.artcraft.photocraft`, GPU fallback, font import, shared fonts, Android SAF open/save, updater, keyboard customization, and tablet enhancements.
- Do not regenerate signing identity, overwrite backups, or expose credentials.
- Verify certificate fingerprint against the existing pinned value in the private workflow, and verify the final APK signer.

## Guarded upstream pipeline — future implementation
1. Poll official tagged upstream releases, resolve tag to an immutable SHA, and detect newer releases.
2. Open a review PR; never automatically overwrite the preserved Android adapter or patches.
3. Diff source and Android enhancements; run compile, feature-preservation, package/version/signing and update-install checks.
4. Fail closed when any check is missing, fails, or reports unported upstream changes.
5. Keep `publishing_enabled: false` and do not auto-publish until explicit authorization after all checks pass.

## Existing branch caution
- `automation/photocraft-upstream-guarded-20261021` diverges from main (38 ahead, 5 behind) and contains 12 changed files, including significant adapter and Java changes.
- Its `.github/photocraft-upstream-automation-policy.yml` is a staging contract and explicitly disables publishing.
- Its release workflow is not a safe drop-in replacement for the private signed workflow.

**This file is a plan only; it changes no production code or workflow.**
