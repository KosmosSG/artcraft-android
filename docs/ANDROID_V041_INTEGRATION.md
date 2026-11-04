# Android v0.4.1 integration — work in progress

This branch stages the shared Android changes from
`MostafaXS1/artcraft-android` at `fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`
(including fixes following v0.4.1). It is **not a replacement release source**.
No signed production APK or physical-device compatibility is claimed.

## Staged source changes

- Document recovery and lifecycle persistence, including PhotoCraft RecoveryStore
  services and the generic per-app persistence recipes (Afnankabiro).
- Session restoration and SAF staged-document mirroring.
- Two-finger gesture scrolling and mobile-density scaling.
- Upstream GPU integration, retaining the existing PhotoCraft CPU preference,
  software-adapter handling and diagnostic fallback messages (RiotJuice and
  upstream contributors).
- Push/PR build workflow with no release-write permission or permanent secrets.

The upstream builder-wide automatic updater is deliberately inactive in this
integration shell: it compares the wrong version scheme and offers APKs from a
different repository. Each app's existing native updater must be preserved from
its released baseline, including manual checks, opt-in startup checks, channels,
exact package/signature/asset filters and Help-menu placement.

## Why this cannot replace released APKs yet

The suite's `main` branch does not contain the complete source of its released
applications. Ten apps have separate published source baselines recorded in
`configs/android-integration.json`; three have no published stable baseline in
the release feed examined. Merging the reference fork into `main` alone would
omit release-specific fonts, keyboard fixes, icons, menus and updater behavior.

The next integration step is to port these shared changes onto **each exact
released source baseline**, reconcile its upstream API changes and run its
existing app-specific regression tests. A generic shell compiling successfully
does not satisfy that requirement. The recorded status fields remain false.

The manifest pins the 13 official Storytold stable releases inspected on
2026-10-28. Both the selected tag and checked-out commit must match. No floating
`main`, tag-sort heuristic, or silent fallback is accepted by this branch.

## Validation and build boundary

Run `python3 tools/test_android_integration.py`, the existing naming and parity
tests, and shell/embedded-Python syntax checks. CI attempts ARM64 compilation
using `com.artcraft.<app>.integration`, a disposable local key, and the pinned
upstream release. It uploads failure logs only, never APKs or GitHub Releases.
Ordinary production-package build invocations fail before toolchain setup.

After app-specific preservation is implemented, verification still requires
the original independent signing certificate, a monotonically higher versionCode,
the established upstream-version-plus-Android-revision naming, APK checksums,
and tests on the exact signed APK. Existing stable releases and app data are
unchanged. Do not mark GPU compatibility or recovery behavior device-verified
without physical-device evidence.
