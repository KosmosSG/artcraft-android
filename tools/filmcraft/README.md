# FilmCraft Android — isolated candidate (AUDIT ONLY)

This folder belongs exclusively to FilmCraft. Do **not** overwrite PhotoCraft,
VectorCraft, DesignCraft or their private signing repositories.

## Verified official release and provenance (22 Oct 2026)

- Official repository: https://github.com/storytold/filmcraft
- Latest stable release observed: `v0.10.0`, published 2026-10-21.
- Tag **resolves to commit** `cdf43fd366e378da266cb6d3c94549a45244be1f`
  (lightweight tag verified through GitHub API).
- Reviewed Android builder reference:
  `MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
  Reference is a *review source*, NOT approved as a wholesale replacement for current
  suite code; MIT attribution applies.
- Suite baseline: `KosmosSG/artcraft-android` main commit
  `7b46f87aba112fff93380e01379045733f09f8b3`.
- FilmCraft source uses MIT OR Apache-2.0 (retain LICENSE-MIT, LICENSE-APACHE,
  NOTICE and required attribution); the upstream NOTICE **excludes its trademarks
  and logos** from those open-source grants.
- This is NOT a built, signed or tablet-tested APK.

## Proposed first package (NOT YET VALIDATED)

- Target: HONOR MagicPad 4, MagicOS 10, `arm64-v8a`.
- Default package identity candidate: `com.artcraft.filmcraft`. Audit any
  existing on-device FilmCraft installation before confirming it.
- Planned versionName: `0.10.0-android.1`.
- Planned filename: `filmcraft-0.10.0-android.1.apk`.
- **versionCode not reserved**: never set one before inspecting *all*
  prior FilmCraft signed/installed/published versionCodes.
- No FilmCraft release, signing repo or suite FilmCraft signing workflow was
  visible to the connected account at audit time. This does NOT prove no
  FilmCraft keystore exists locally or outside connected GitHub. Never overwrite
  or rotate a previously used certificate.
- Do not use PhotoCraft's, VectorCraft's or DesignCraft's permanent keys.
- Current generic `lib/build-common.sh` creates `keys/artcraft-builder.jks`,
  so this key is only fit for a **disposable, unpublished, ephemeral test**.
- The present builder also follows upstream versionName instead of this policy.
  **Do not run it as a production FilmCraft signed-release workflow.**

## Ported candidate source code (not APK-verified)

FilmCraft-only source overlay now exists on this branch:

- `tools/filmcraft/FilmCraftActivity.features.java.inc`: Android SAF picker for
  TTF/OTF, persisted shared tree-URI permission (recursively scans subfolders),
  app-private cache, guarded GitHub FilmCraft release check and saved opt-in
  startup update preference.
- `tools/filmcraft/filmcraft_features.rs`: registers fonts with
  `filmcraft_text::fonts::add_font_data`, restores private fonts at startup,
  loads/refreshes shared fonts, draws a docked non-floating feature toolbar
  and reports update/error states without silent APK installation.
- `tools/filmcraft/runtime_patch.py`: fail-closed FilmCraft-only wiring into
  the builder-generated Java, Rust and Cargo manifest. Adds INTERNET solely to
  FilmCraft. `lib/build-common.sh` conditionally invokes it only when
  `APP=filmcraft` after generation. The source guard validates static API
  names, Python syntax and Rust syntax.

The toolbar currently provides direct access to the FilmCraft-only features
instead of modifying the upstream Help menu. An optional Help-menu entry can
follow after versioned upstream UI API integration.

**Source staged ≠ Android build passing ≠ device behavior confirmed.**
No compile/build/device test has yet demonstrated this feature overlay works.
Do not describe these as working on MagicPad until a bounded Android build and
the user's on-device tests pass.

## Actual upstream interfaces and port priority

1. **Preserve** `filmcraft_ui_egui::FilmcraftApp::new(Session::default())` and
   its `HostHooks`; the current builder's FilmCraft SAF recipe already maps
   `run_dialog`, `pick_files`, `pick_folder` and imported files. Validate
   content URI lifetimes and separate large video/audio media staging; do not
   assume a simple copied document works for streaming/scrubbing/export.
2. Reuse FilmCraft's existing keyboard-shortcut editor and command registry
   instead of creating conflicting mappings. Check modifier tracking, IME
   composition, and optional docked touch Shortcut Pad on a device.
3. The caption/title UI uses `filmcraft_text::families()` and system font scans.
   Test native TTF/OTF loading and Android SAF shared-font folders against that
   exact API, then add import without a floating custom-font window.
4. Preserve playback/audio and CPU render/export; upstream's desktop
   `set_wgpu` and GPU-export registration do not prove Android GPU availability.
   Diagnostics must report the **actual** adapter/device/mode and failed
   fallbacks without fabricating GPU acceleration.
5. Evaluate tablet scaling, pointer, multi-touch, stylus behavior with the
   real FilmCraft timeline UI before asserting support.
6. Update checks: manual Help-menu action plus saved startup preference,
   distinguishing official upstream source version from signed Android APK
   version and reporting failures/offline state.
7. Port incrementally with isolated commits, appropriate licensing and
   preservation tests, then build once in a bounded CI job with an ephemeral
   key, inspect compiled Activity/SAF, manifest/package/versionCode, certificate
   fingerprints, native ABI and SHA-256.

## Uploaded icon integration status

**The user-supplied Fc picture is the design source**, not an AI recreation.
Original source SHA-256:
`242c40a9c5d508f75a771ece0cb8e4f741c914f7af20e46eb5e06f09e845764d`.
Android mipmap and adaptive assets were prepared separately from the exact
uploaded image; they have **not yet been committed to the repository** and
are **not in an APK**. Do not substitute the unrelated default FilmCraft icon.
When assets are available inside the GitHub branch, review and add all mipmap
sizes, foreground/background/adaptive XML and verify they are present in the
APK with exact visual appearance. Do not use preview image bytes as proof
of APK integration.

## Signing and future automation gates

- First inspect existing FilmCraft APK artifacts, published releases, packages,
  versionCodes and any pre-existing signing certificate + encrypted backups.
- Only if no permanent identity exists anywhere, create a **FilmCraft-only**
  permanent signing identity, secure secret storage and encrypted offsite backup.
- Confirm approved source/tag/commit, non-regressing features, clean build,
  correct manifest/package/versionCode, signer fingerprint and reproducible
  payload hash; do not re-sign by silently mutating the APK payload.
- Only then consider automatic upstream detection, guarded compatibility build,
  verified release and corresponding updater metadata. Never overwrite tags,
  enable release publishing, or activate main-branch schedules as part of this PR.
- `upstream_guard.py` is **read only** and cannot sign, build or publish.
  It checks tag mutation and indicates when a new upstream release needs review.

**All feature work above remains pending until implemented and tested.**
