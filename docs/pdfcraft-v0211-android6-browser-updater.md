# PDFCraft v0.21.1 Android.6 — production-capable browser-only updater candidate

## Owner-confirmed Play Protect findings (13 Nov 2026, HONOR MagicPad 4 / MagicOS 10)
| Signed APK | Broad storage | APK installer permission | Play Protect |
|---|---|---|---|
| Android.2 | yes | yes | Harmful app blocked |
| Android.3 | no | no | This app looks safe |
| Android.4 | yes | no | PASS |
| Android.5 | no | yes | Harmful app blocked |

These diagnostic A/B observations strongly implicate `REQUEST_INSTALL_PACKAGES` and/or installer behavior; they do **not** independently certify the APK or reveal Google's exact classification rationale. Keep Play Protect enabled and do not bypass a harmful-app warning.

## Committed source-level changes
- Remove `REQUEST_INSTALL_PACKAGES` from PDFCraft's generated Android manifest permanently, leaving the unrelated suite apps untouched.
- Replace PDFCraft-only in-app APK download and PackageInstaller code with disabled compatibility hooks, deliberately eliminating PackageInstaller and DownloadManager usage in the appended updater Java source.
- Remove both **Download APK** and **Install downloaded APK** buttons from PDFCraft's native Rust update UI. The user instead opens the exact GitHub Release page in an external browser.
- Retain GitHub Releases update detection, toast notifications, startup update-check preference, in-app "View GitHub release" links and About/build identity.
- Preserve `MANAGE_EXTERNAL_STORAGE` in this candidate, as requested to retain existing direct file-browsing functionality, alongside SAF document/folder selection.
- Preserve upstream PDF editor, offline OCR models, fonts, stylus wheel, keyboard and lifecycle integrations; these still require device regression testing.
- Update source-level adapter and updater regression tests to assert browser-only update behavior and absence of installer APIs.

## Build / signing
Development branch: `fix/pdfcraft-v0211-android6-browser-update-20261113`
Workflow: `.github/workflows/pdfcraft-v0211-android6-browser-only-signed-test.yml`
Package: `com.artcraft.pdfcraft` (the **real** release app, not a separate test package)
Version: `0.21.1-android.6`, versionCode `16782598`
Signer: **existing original PDFCraft permanent certificate**, verified against public Android.1 APK.
Output: **GitHub Actions signed TEST artifact only**. No new public release, signing-key reset or automatic promotion.

The workflow retains pinned upstream/source verification, Rust/Python/Java regression tests, OCR tests, ARM64-only ZIP checks, source/package identity guards, exact Android permission auditing, APK payload verification before/after signing and certificate comparison with Android.1.

## Required acceptance gate
1. Download the complete signed Android.6 Actions ZIP and extract the exact signed APK. Record its SHA-256 from artifact metadata.
2. With Play Protect **enabled**, test the APK on HONOR MagicPad 4. **Do not install anyway** if "Harmful app blocked" appears.
3. If Play Protect says "This app looks safe", exercise PDF open/edit/save/reopen, PDFs via SAF and direct storage browser, font folder import, OCR, stylus hover/wheel/customization, hardware keyboard D/C/S and relaunch, update checks and opening the GitHub Releases page. There should be no in-app APK install/download buttons.
4. If any tested capability is broken, fix and rebuild. Do not release without another complete check.
5. **Publication is disabled** until owner explicitly approves the exact signed and device-tested artifact. When approved, publish only those exact bytes; do not rebuild/re-sign in the publishing stage. Ensure compatible higher versionCode and certificate SHA-256.

No claim is made that a Play Protect pass proves the APK has no security vulnerabilities.
