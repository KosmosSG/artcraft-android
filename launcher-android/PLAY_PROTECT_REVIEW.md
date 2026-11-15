# ArtCraft Launcher — Google Play Protect review (official Android.10)

**Status:** A user reported that Google Play Protect displays **"Harmful app blocked"** when trying to install the official permanent-signed `ArtCraft Launcher v0.1.0-android.10` APK (screenshot dated 2026-11-15). The cause **has not been established**, and this warning must not be treated as an ordinary unknown-source prompt.

## Source-level preliminary review

- Official Android.10 GitHub Release: https://github.com/KosmosSG/artcraft-android/releases/tag/artcraft-launcher-v0.1.0-android.10
- Release source commit: `6adc2d9168338c3d879ecee422cd79bebe41bf01`, built as release variant and permanently signed by the guarded workflow
- Declared Android permissions: `android.permission.INTERNET` and `android.permission.REQUEST_INSTALL_PACKAGES`
- The launcher needs Internet permission to query public GitHub Releases and request HTTPS downloads; it uses DownloadManager for per-app APK downloads
- `REQUEST_INSTALL_PACKAGES` is necessary for the launcher’s user-initiated in-app APK installation feature; Android's system package installer still requires user confirmation
- No SMS, accessibility service, notification listener, account, location, microphone, contacts or other sensitive data-access permissions are declared in the inspected source manifest
- No third-party runtime SDK dependencies are declared in the inspected Gradle file; JUnit is a test-only dependency
- The code checks the release SHA-256, package name, installed-app signing certificate and versionCode before asking Android to install the downloaded app
- The release workflow checked the permanent signer against official Android.9 and passed, but **valid signing and correct checksums do not prove the APK is safe**
- Additional audit is needed to rule out malicious functionality, unintended behaviors, or third-party risk. The observed Play Protect classification cannot be diagnosed with certainty from source inspection alone

## Safer user experience

Android.11 TEST changes the two fully teal menu bars into compact dark update controls. It also removes the automatic installer launch when returning to the app; installs remain explicitly user-initiated. Neither change is represented as a Play Protect fix, and none is intended to hide the app’s functionality from security review.

## Official Google guidance and developer appeal

Read Google's guidance: https://developers.google.com/android/play-protect/warning-dev-guidance

Google's appeal form: https://support.google.com/googleplay/android-developer/contact/protectappeals

The form requests the package name (`com.artcraft.launcher`), the **APK's own SHA-256 hash** (not the certificate fingerprint), a VirusTotal upload/report of the APK, and a description of the review. An owner should confirm the official APK binary and perform appropriate safety checks before submitting an appeal. Do not share the keystore/private signing key or passwords in the appeal.

**Keep Play Protect enabled and do not suggest "Install anyway" while the detection remains under investigation.** The Google Play Protect appeal process determines whether Google will reconsider its classification. Do not publish another production-signed build solely as an attempt to evade a detection.
