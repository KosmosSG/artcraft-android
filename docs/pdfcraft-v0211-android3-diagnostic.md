# PDFCraft 0.21.1-android.3 — **temporary minimal-permission diagnostic APK**

## Context
The exact original-certificate signed Android.2 APK was rejected by Google Play Protect on HONOR MagicPad 4, 13 Nov 2026 at 15:41 Malaysia time. This finding does not implicate the signing key or GitHub hosting and is not a malware verdict.

- Blocked Android.2 Actions run: https://github.com/KosmosSG/artcraft-android/actions/runs/43384697045
- APK SHA-256 (from artifact SHA256SUMS.txt): `7d3341c2a1a207a46b77c1092f539abf5a5103c819c7ed186aabda7371d4980a`
- Original signer certificate SHA-256: `be7254670cf0d451a17dd7ad8462ada3f806e50ab296d78a5db685e2a30a849f`
- GitHub source: https://github.com/KosmosSG/artcraft-android/pull/161
- **No publication of Android.2.**

## Diagnostic hypothesis
The Android.2 APK has broad file access (`MANAGE_EXTERNAL_STORAGE`) and the capability to request installation of other APKs (`REQUEST_INSTALL_PACKAGES`). The direct-file browser and user-confirmed in-app update installer currently use these. They are legitimate code paths with user interactions, but their scope merits review and narrowing; **neither permission has been proven the cause of Play Protect classification**.

The Android.3 *diagnostic-only* workflow removes both permission declarations in its **temporary runner checkout** and turns the broad-storage permission request and in-app APK download/install actions into informative no-ops.

- `INTERNET` and legacy storage permissions remain to preserve most existing app behaviour.
- Native PDF rendering, annotation, OCR, fonts via SAF, stylus wheel and document picker are intended to remain. This is not a guarantee of full hardware functionality.
- Browsing files via paths requiring broad permission may fail; importing via Android Storage Access Framework should be used.
- Update notifications/checks may still display; in-app APK installation and APK downloading are disabled.
- Production package remains `com.artcraft.pdfcraft`, versionCode `16782595`, and original signing identity is preserved so installer screening is comparable to the blocked production package.
- Workflow runs tests and verifies final package/signer/version/ABI and all 3 remaining permissions. No GitHub release is created.
- This **experiment must not be promoted or merged as a production change** without complete functionality and security reviews.

## Device test
1. With Google Play Protect enabled, download **only** the diagnostic Actions artifact from the successful workflow.
2. Record whether Play Protect still displays `Harmful app blocked`. **Do not choose Install anyway as a test pass.**
3. If warning remains: stop diagnostic release efforts and provide the exact Android.3 APK SHA-256 (from the new artifact) to Google Play Protect appeals. Do not infer a harmless false positive.
4. If warning disappears: that is only an indication to perform controlled, single-permission follow-up comparisons and functionality audits, not sufficient proof of safety or clearance of a final feature-complete build.
5. Public releases, original signing secrets, Android.1/Android.2 artefacts remain unchanged.

Google Play Protect guidance: https://developers.google.com/android/play-protect/warning-dev-guidance
Google appeal: https://support.google.com/googleplay/android-developer/contact/protectappeals
Android restricted all-files access: https://developer.android.com/training/data-storage/manage-all-files
