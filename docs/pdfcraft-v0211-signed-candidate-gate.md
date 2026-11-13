# PDFCraft v0.21.1 Android.2 — exact production-signed APK test and publication gate

## Why this exists
On 2026-11-13 the owner reported that a PDFCraft Android.1 test installation passed scanning but the released APK showed **Google Play Protect: Harmful app blocked**. The earlier security audit also recorded an older test APK receiving a Play Protect warning, so neither broad statement ("all test packages pass" / "all signed packages are blocked") is established. Google has not disclosed the APK's harmful-app category.

Prior workflows rebuilt PDFCraft with the production application ID and original permanent signer after testing a disposable-key APK using a different application ID. Consequently the prior APK test was not a validation of *exactly the same signed binary* that was published.

The Android.1 stable release remains published, unchanged, and Play Protect classification is unresolved:
- Exact APK: https://github.com/KosmosSG/artcraft-android/releases/tag/pdfcraft-v0.21.1-android.1
- SHA-256: `e7c6af7b452c9270be648a01138cb5295ee156f4507aac067c8cbcb7a1092966`
- Package: `com.artcraft.pdfcraft`
- Version: `0.21.1-android.1`, versionCode `16782593`

## Reviewed permission inventory
The prior released APK requests:
- `INTERNET` — repository update checks and downloads.
- `REQUEST_INSTALL_PACKAGES` — **actually used** by a user-initiated verified in-app updater using PackageInstaller. Do not remove without replacing or disabling that flow.
- `MANAGE_EXTERNAL_STORAGE` — **actually used** by the direct file browser and optional "All files access" prompt. SAF user-granted documents/folders are supported in parallel. Do not remove without completing and device-testing a SAF-only replacement.
- `READ_EXTERNAL_STORAGE` (maxSdk 32) and `WRITE_EXTERNAL_STORAGE` (maxSdk 29) — compatibility with legacy storage behaviours.

The signed Android.2 candidate enforces this known inventory and refuses unreviewed permissions; this is *not* a statement that these permissions are harmless or why Google flagged the app. The two broad permissions need a future functional migration to narrower APIs if feasible. Do not claim the warning is a false positive, that signature alone caused it, or that CI provides a malware verdict.

## Build the exact Android.2 production-signed candidate
Workflow: `.github/workflows/pdfcraft-v0211-android2-signed-test.yml`
Branch: `fix/pdfcraft-v0211-android2-signed-candidate-20261113`

CI uses the tested source and upstream pin, rebuilds Android.2 with the **real production package `com.artcraft.pdfcraft`**, versionCode `16782594`, and the **existing PDFCraft permanent signer**. It validates the installed certificate fingerprint against Android.1; verifies source, ZIP, ABI, package, permission inventory, OCR and signing invariants; and uploads a **private-to-the-run Actions test artifact**, without creating a GitHub Release.

Artifact name: `PDFCraft-v0.21.1-android.2-PERMANENT-SIGNED-TEST-ONLY`
APK file inside: `PDFCraft-v0.21.1-arm64-release.apk` (same filename required by the existing in-app updater's release pattern).

The generated SHA-256 is not known until successful build. Use the sha256sum file in the artifact. **This is still a candidate, not a security certification.**

## Device test gate
Before publication, on HONOR MagicPad 4 with Play Protect enabled:
1. Determine whether Play Protect prompts to scan or classifies the **exact permanent-signed Android.2** APK as harmful. Preserve the full warning and any expanded details.
2. If Play Protect blocks it, **STOP**. Do not click *Install anyway* to pass the gate. Escalate with the exact signed APK hash using Google's Play Protect appeal process. Do not public-release this APK.
3. If Play Protect is clear, exercise local PDF open/save/reopen, document picker and direct-file browser, font import/folder scanning, offline OCR, wheel hover and assignment/opacity sliders, hardware keyboard relaunch, and update-check + PackageInstaller user confirmation.
4. Record the exact test run ID, source SHA and **signed** APK SHA-256. The ephemeral Android.1 test APK is not interchangeable.

## Manual release — only after clearance and owner approval
A separate **manual-only** publisher lives on the repository's default branch:
`.github/workflows/pdfcraft-v0211-android2-manual-promote-signed.yml`.
It accepts the successful signed-test run ID, exact source commit SHA, exact signed APK SHA-256, and the confirmation `PLAY_PROTECT_CLEAR_AND_OWNER_APPROVED`.

The publisher re-downloads and validates that **exact Actions artifact**, verifies source provenance and signing identity, validates package/version/ABI/permissions/ZIP integrity, and uploads *the same file bytes* to a new, immutable release tag `pdfcraft-v0.21.1-android.2`. It never rebuilds or re-signs the APK and never overwrites an existing tag. Publication is **not automatic** and must not be triggered if the Google warning persists.

## Interpretation
A passing scan of a distinct test package is not proof that a later rebuilt production app is cleared; a harmful-app warning is not explained by the signing step merely because it appears on a published APK. Review actual APK behavior, manifest, native dependencies, and Google's classification before further public deployment.

References:
- https://developers.google.com/android/play-protect/warning-dev-guidance
- https://developer.android.com/training/data-storage/shared/documents-files
- https://developer.android.com/training/data-storage/manage-all-files
- https://support.google.com/googleplay/android-developer/contact/protectappeals
