# ArtCraft Android Suite — Release Size and In-App Updater Contract

Applies to PhotoCraft, VectorCraft, DesignCraft, EffectCraft, LightCraft,
PDFCraft, WordCraft, DeckCraft, GridCraft and FilmCraft.

## Baseline and compatibility

- Start from each app's latest approved, published working release.
- Preserve original package ID and signing certificate for in-place upgrades.
- Never change another Craft app while preparing an app-specific candidate.
- Never replace a published signed APK or rotate a signing key to fix updates.
- Keep all approved SAF fonts, keyboard, gestures, stylus, recovery, GPU,
  appearance, app icon and updater functionality.
- Use a different test package and disposable key until owner device testing.
- No permanent signing or publication of a new APK before owner approval.

## Size optimization (safe, measurable)

1. Analyze the baseline and candidate with:
   python3 tools/android_apk_size_audit.py candidate.apk --arm64-only --baseline-bytes BASELINE_SIZE --max-growth-percent 3 --report size-report.json
2. Remove unnecessary test and debug assets from the staged production package.
   Prefer release-profile native builds with debug information stripped after
   retaining appropriate private crash diagnostics; never strip needed runtime
   resources or break ELF native-library loading.
3. Package only arm64-v8a for the main HONOR MagicPad 4 build. Perform
   compatibility checks for other devices rather than assuming all support ARM64.
4. Optimize font asset bundling, duplicated icons and unused images, preserving
   approved glyph/icon fidelity, dynamic SAF fonts and mandatory licenses.
5. Do not enable aggressive size or compression flags without GPU/performance,
   startup and functionality regression tests. Do not unzip/rezip signed APKs:
   zipalign/signature and native-library page alignment can break.
6. Compare real APK size and critical performance with the published baseline.
   A size gain must not regress launch, 165Hz frame pacing, documents or input.

## In-app updater (required for every app)

- Keep Check Updates, optional Startup Update Check and Download in app
  inside the compact app icon menu. A startup check must be opt-in and silent
  unless a valid, newer update exists.
- Resolve published, non-draft, stable releases for the correct app tag prefix.
- Every release must include an update manifest such as designcraft-update.json
  with schema, package, version name/code, expected original certificate,
  APK SHA-256, canonical release APK URL and source SHA. Verify that manifest
  and APK are both attached before publication.
- Download APK through Android without handing off to a web browser.
  Show progress, cancellation, errors and retry options. Avoid unbounded RAM,
  storage or file sizes.
- Verify SHA-256, original APK signing certificate, package ID, monotonic
  versionCode, expected versionName and target ABI before installation.
- Use Android's normal user-confirmed install flow; no silent installs, no
  destructive data clearing. Display guidance if install-from-this-source
  permission is missing.
- Never offer production updates to separately signed test packages.
- Keep network and download work off the UI thread; handle cancellation and
  Activity recreation safely.
- Check updater compatibility from the previous installed version: publishing
  a new APK alone is insufficient if earlier updaters require a metadata asset.
- Do not distribute metadata claiming checks not actually performed.

## Current DesignCraft pilot

Branch: feature/designcraft-v019-inapp-downloader-size-policy-20261110

- Existing read-only release finder preserved.
- Production-only verified Android DownloadManager flow added in Java.
- Android installer is launched only after checksum, certificate, package,
  version and ARM64 engine checks. The user must confirm installation.
- Test packages cannot use the permanent production update channel.
- Source integration, Android compilation and HONOR MagicPad 4 runtime behavior
  are not yet proven. Do not mark the pilot complete until a real APK build
  and device install/download/update test succeed.
- The already published v0.19.0-android.1 release lacks designcraft-update.json.
  Attach the separately verified manifest without replacing its APK so the
  older app can detect it.
- No test candidate has been permanently signed and no release changed by pilot.
