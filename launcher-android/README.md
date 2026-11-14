# ArtCraft Android Launcher (prototype)

An **independently installable** native Android dashboard for the 13 Craft apps in the KosmosSG Android suite. This project lives in its own `launcher-android/` subfolder and an isolated feature branch. The existing Rust app builders, main branch, published releases and permanent signing keys are left alone.

## v0.1.0-android.9 scope
- Responsive tablet grid with all 13 products (including unreleased placeholders).
- Detect app packages and launch installed apps without accessing their private data.
- **Self-updater:** the overflow menu offers manual `Check Launcher Update` plus a separate persisted **OFF-by-default** launcher-startup toggle. It looks for exact `artcraft-launcher-vX.Y.Z-android.N` releases with one signed `ArtCraft-Launcher-vX.Y.Z-android.N-arm64-v8a.apk` asset and `SHA256SUMS.txt`, excludes drafts, honors the Stable/Preview channel, compares versions, and uses the existing in-app download, SHA-256, signer, package, versionCode and user-confirmed installation path. No qualifying published launcher release exists until the owner explicitly publishes one with permanent signing. Existing *disposable debug-signed* tests are not guaranteed in-place compatible.
- Manual and opt-in startup update checks using the **public** `KosmosSG/artcraft-android` GitHub Releases API. Startup checking is **off by default**.
- Stable and Stable + Preview release channels (default: Stable + Preview). Drafts, unrelated apps and mismatched APK asset names are excluded.
- Download an explicitly selected APK using Android DownloadManager, with **live in-app progress, percentage/bytes, cancel, verification status and Install button**, without sending the user to a browser. Verify the release SHA-256, inspect APK identity and versionCode and compare an installed app's signing certificate before asking Android's installer to proceed. No silent installs, uninstalls or data changes.
- System light/dark theme, no runtime dependency on AndroidX or Compose, no Rust, minimal APK size.

The ArtCraft Launcher uses the user's supplied multicolor `Ac.png` artwork for both the **Android home-screen APK icon and the top-left in-app header emblem** (optimized high-quality WebP at `drawable-nodpi/ac_brand_icon.webp`). The app has a neutral gray dark/light color system, with **one consistent teal** for primary action buttons, secondary outlines, download progress, and status highlights. Each **installed** suite app card now displays the actual Android app icon returned by PackageManager, matching the artwork already visible in the HONOR launcher (including illustrated FigCraft, SoundCraft, CADCraft and other app icons). When an app is not installed or its icon is inaccessible, its card safely falls back to the previous Ac-style initial badge. This reads installed app metadata only; it does not change any managed APK. Browser links point only to real release pages.

## Build
Use the one-off GitHub Actions test workflow `.github/workflows/artcraft-launcher-test-apk.yml`, or build locally with Java 17, Android SDK 35 and Gradle 8.10.2:

```sh
gradle -p launcher-android testDebugUnitTest assembleDebug
```

The output is `launcher-android/app/build/outputs/apk/debug/app-debug.apk`. It is **Android debug-key signed, TEST ONLY** and must not be distributed as a production release or upgraded to a different key without a deliberate migration.

## Security and release policy
- Never install a package unless the user approves the Android system installer.
- A downloaded APK without a matching per-asset SHA-256 entry is rejected.
- Reject mismatched `applicationId`, non-increasing `versionCode`, and a mismatched existing signing certificate.
- The APK installer checks certificate/signature correctness. Installing apps from GitHub requires explicit user trust.
- GitHub API rate limits and offline failures are reported; they do not block app launch.
- Some older published APKs use noncanonical or reused filename/metadata and will deliberately not appear as eligible one-tap updates; the release page remains available.
- This prototype is **source-built but not physically device-verified** on a HONOR MagicPad 4. Do not mark it device-verified until user testing.

Android.9 OLED pure-black dark mode: page, surrounding card gutters, top header, status/navigation bars, bottom notification bar, and overflow menu use #000000. App cards (#30363B), hero (#353C41), high-contrast borders (#717B83), readable text, and teal-only actions remain unchanged. Optional light theme remains available. The original Ac icon, 13 installed app icons, in-app download verification and launcher self-updater remain intact.

Potential follow-up: Update All queue, permanent launcher signing and a truly separate `KosmosSG/artcraft-android-launcher` repository, which requires repository-creation permissions.
