# LightCraft v0.18.0 Android — protected upstream integration

**State:** Active integration preflight. **No v0.18.0 ARM64 test APK exists yet.**
**Scope:** LightCraft only. No edits to the other ArtCraft app source, secrets, or releases.
**Branch:** `feature/lightcraft-v0180-android-test-20261104`.

## Protected Android baseline

- Start from published `lightcraft-v0.11.0-android.8` at `7496af6c95e4bf6c1a1be6586838801f193ed749`. This is a permanently signed, **untested preview**, not a device-approved stable build.
- Preserve the last release explicitly described as stable, `lightcraft-v0.11.0-android.6`, as rollback. **Do not delete, replace, update or auto-promote either release.**
- Preserve the exact user-approved glossy LC image (`assets/lightcraft/lc-user-approved.png`, SHA-256 `8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4`), MagicOS-safe adaptive resource handling, native header logo, Help/About update UI, preview/stable channel selection, startup checks, safe download behavior, SAF photo import and non-clobber export, RAW/ICC/color pipeline, photo library/session, touch/trackpad, keyboard, GPU, AI and approved performance optimizations.
- Keep original production package and signing identity **out of test builds**. Do not touch keystores, production secrets or app data.

## Official upstream target

- Official `storytold/lightcraft` stable release: `v0.18.0` (2026-11-03 00:54:20 UTC), immutable commit `32d569ad5d19a6b55cf8d5c077127faa0f44a83b`.
- Rust MSRV: 1.95; egui/eframe: 0.37; workspace version: 0.18.0.
- New changes include histogram percentile-zero behavior, safety validation for shutter fractions and GPU limit values, library date search case-insensitivity, survey Ctrl-click, linkMargins preservation, and optional software-adapter GPU equivalence tests. Review import/export and Android event handling before enabling.
- Preserve earlier source-only drafts PR #107 (v0.16.0) and #111 (v0.17.0) as research; neither establishes a working Android port. PR #44 records approved icon behavior.

## Port blockers — do not burn GitHub Actions minutes yet

1. The v0.11.0-specific `tools/lightcraft/apply_android_fixes.py` edits `crates/ui-egui/src/menus.rs`, `src/menubar.rs` and `panels/dialogs.rs`; v0.18.0 moved controls to `menus/ui_commands.rs`, `menus/menubar.rs` and `dialogs/updates_ui.rs`. Adapt the Android updater integration instead of running old string replacement blindly.
2. v0.18.0 `Services` requires `write_new` in addition to existing write and shared-write flows. A safe, fail-closed v0.17-era Android-only create-new patch and offline tests were copied to this branch; review against the exact selected builder, and **never overwrite a SAF-picked URI** with a create-new operation.
3. Compare the approved Android builder `MostafaXS1/artcraft-android` (legacy commit `ac54d62...`) with newer reviewed commit `fbb4f66...`; retain working activity, keyboard, touch/scrolling, IME, native libraries and SAF path provenance. Resolve API, feature and dependency mismatches rather than replacing the Android implementation.
4. Review Rust 1.95 and eframe 0.37 Android compatibility, all required native libraries and GPU fallback. Preserve image-editing quality, RAW/HEIC/DNG/ICC, watermark and export functionality.
5. Do **not** set `gates.android_api_port_complete` to true in `configs/upstream/lightcraft-v018.json` until the actual Android port and lightweight checks pass. `tools/lightcraft/verify_v018_contract.py --require-android-port` must fail before that stage.

## Build, verification and owner approval gates

- Run source provenance and offline regression tests first; only then use one cached ARM64 build attempt. No build per minor edit, production signing workflow, tag, release, merge to production, or auto-publish.
- Target **LightCraft v0.18.0-android.1 TEST** and `com.artcraft.lightcraft.test` when practical; use an ephemeral/disposable signing identity only. Protect the existing `com.artcraft.lightcraft` installation and all data.
- Verify actual APK: ARM64 (`lib/arm64-v8a/*.so`), valid Java Activity/dex and launcher, version, package identity, signature different from production, SHA-256, adaptive/legacy icon, touch/IME/input paths and no embedded production keystore.
- Test on HONOR MagicPad 4: open and edit photos; SAF select/import and save/export; preserve names and overwrite safety; RAW/ICC/watermark; scrolling/gestures/keyboard/ESC and dialogs; GPU/performance; original LC icon and header; Help/About channel and updates; persistent settings; no interference with installed stable app.
- Share the **actual artifact link** and test checklist. Stop for physical-device test report, then separate explicit owner approval before permanent signing, then separate explicit owner authorization before publishing.

`configs/upstream/lightcraft-v018.json` is a target/provenance lock, **not** proof of Android build parity or APK availability.
