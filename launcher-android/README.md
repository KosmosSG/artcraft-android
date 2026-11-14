# ArtCraft Android Launcher (prototype)

An **independently installable** native Android dashboard for the 13 Craft apps in the KosmosSG Android suite. This project lives in its own `launcher-android/` subfolder and an isolated feature branch. The existing Rust app builders, main branch, published releases and permanent signing keys are left alone.

## v0.1.0-android.2 scope
- Responsive tablet grid with all 13 products (including unreleased placeholders).
- Detect app packages and launch installed apps without accessing their private data.
- Manual and opt-in startup update checks using the **public** `KosmosSG/artcraft-android` GitHub Releases API. Startup checking is **off by default**.
- Stable and Stable + Preview release channels (default: Stable + Preview). Drafts, unrelated apps and mismatched APK asset names are excluded.
- Download an explicitly selected APK with Android DownloadManager, verify the release SHA-256, inspect APK identity and versionCode and compare an installed app's signing certificate before asking Android's installer to proceed. No silent installs, uninstalls or data changes.
- System light/dark theme, no runtime dependency on AndroidX or Compose, no Rust, minimal APK size.

The in-app tiles now share the same **Ac-inspired rounded-square, tonal gradient, white sans-serif lettering and subtle outline**. Each of the 13 apps retains its own initials and accent color; this changes launcher dashboard tiles only and does not modify the separate ArtCraft APK launcher icons. Final approved per-app artwork can replace these in a later revision. Browser links point only to real release pages.

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

Potential follow-up: individual app-approved icons, download progress & update-all queue, permanent signing and a truly separate `KosmosSG/artcraft-android-launcher` repository, which requires repository-creation permissions.
