# ArtCraft Android Suite conventions

Agreed with the user on 2026-10-21. Apply to all upcoming ArtCraft Android Suite apps.

- Display version: `<official-version>-android.<revision>`.
- APK filename: `<appname>-<official-version>-android.<revision>.apk`.
- Example: `vectorcraft-0.14.0-android.1.apk`.
- Start Android revisions at `android.1` for each new official upstream app version.
- Increment to `android.2`, `android.3`, etc. for Android enhancements or fixes to that same upstream version.
- Always increase Android's internal versionCode across updates, even when the Android revision restarts for a new upstream version.
- Use official storytold app releases as app source. Review Android builder changes against MostafaXS1/artcraft-android commit ac54d62d9d2d6f663295a4afd8972a7a3e79f9af.
- Preserve existing enhancements, package identity, and signing certificates. Do not assume signing keys are shared between apps; establish a permanent key only after resolving whether an existing identity must be preserved.
- Keep each app's development isolated on its own branch and check existing branches/builds first.
- Preserve existing PhotoCraft releases, branches, workflows, and running builds. This document does not migrate or rename existing releases.
- VectorCraft baseline priority: fonts/font import, file open/save, and keyboard support; verify the APK and confirm device behavior before assessing additional tablet enhancements.
