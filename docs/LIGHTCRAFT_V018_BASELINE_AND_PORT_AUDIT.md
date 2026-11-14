# LightCraft v0.18.0 — compatibility and protected-baseline gate (2026-11-04)

**Scope: LightCraft only. Source review, not an installable APK.**
**Development branch:** `feature/lightcraft-v0180-android-test-20261104`
**Status:** `BLOCKED_AT_ANDROID_PORT_AND_DEVICE_APPROVAL_GATES`.
Do not run an ARM64 APK workflow until the items below are resolved.

## Release provenance and source ancestry

- Last published LightCraft Android APK: `lightcraft-v0.11.0-android.8`, tagged commit `7496af6c95e4bf6c1a1be6586838801f193ed749`. Its release notes explicitly call the **exact 72,322,038-byte APK** an **UNTESTED PREVIEW**. Its test/production signing identity must never be reused for temporary candidate signing.
- Previous regular/stable LightCraft Android release: `lightcraft-v0.11.0-android.6`, tagged commit `1cc86e06bd0b56a55167768439bbf691a302cd7a`. Its release notes state HONOR MagicPad 4 validation of the updater UI was **not independently confirmed**. Keep the release as rollback, not as evidence of complete device testing.
- The `android.4` release description reports `android.3` was installed and tested by the owner, but does not establish approval of later UI/icon/updater modifications.
- The `v0.18.0` development branch **is directly descended from the published `android.8` tag** (merge base `7496af6...`, 0 behind). This verifies ancestry, **not** that `android.8` passed device testing. Do not represent it as a verified *tested and owner-approved* working baseline until that separate requirement has evidence.
- Official upstream: `storytold/lightcraft` release `v0.18.0`, tag commit `32d569ad5d19a6b55cf8d5c077127faa0f44a83b`, published 2026-11-03. Rust MSRV 1.95, egui/eframe 0.37.
- Existing release tags, historical APKs, signatures and owner data are immutable for this task.

## Completed evidence — read-only checks only

GitHub Actions run [41761372313](https://github.com/KosmosSG/artcraft-android/actions/runs/41761372313), commit `606a70ae2547df3ff34f6837ef2bfc55d4a5a558`:
- Successful checkout of exact tagged upstream source and reviewed Android builder.
- Python syntax checks: successful.
- Five offline regression tests for fail-closed `write_new` builder patch: passed.
- Source-contract checks: `source_contract_verified=true`, no missing anchors.
- Crucially, `android_api_port_complete=false`, `arm64_apk_built=false`. **No APK was produced.**
- The workflow artifact is a JSON source-compatibility report, **not** an Android APK.

## Concrete Android-port incompatibilities to resolve before a costly build

1. **Updater and Help/About UI:** Published Android `tools/lightcraft/apply_android_fixes.py` targets v0.11 source paths `crates/ui-egui/src/menus.rs`, `crates/ui-egui/src/menubar.rs` and `crates/ui-egui/src/panels/dialogs.rs`. Upstream v0.18 uses `menus/ui_commands.rs`, `menus/menubar.rs`, and `dialogs/updates_ui.rs` with `app.checkForUpdates`. Blindly applying old replacements is forbidden. Preserve LightCraft's approved **Help/About Updates tab**, stable/preview channel preference, nonblocking startup checking, LightCraft-only release filtering, installation safety and visible feedback. Upstream desktop automatic/self-updating cannot replace the Android user-controlled APK update flow.
2. **SAF export contract:** Upstream `Services` includes `write_new` as well as `write` and `write_shared`. Reviewed Android builder has existing `write` and SAF mirror/commit logic, but no verified `write_new` implementation. The new offline patch currently accepts create-new in app-private directories and refuses `media/` staged SAF paths to prevent overwriting a picker-chosen URI. This protects files but **is not proof that every upstream export workflow works**; validate export/save-as behavior and fail rather than silently overwrite.
3. **Android host integration and versioning:** Validate `LightcraftApp::new(Session::new().with_fs(), Services::default())`, `Ui::ui`, asynchronous picker callbacks, touch/trackpad, physical keyboard/IME, storage, and native library boundaries against v0.18 egui/eframe 0.37 and Rust 1.95. Preserve all previously approved adapter improvements, not just successful compilation.
4. **Graphics and photo quality:** Verify native ARM64 libraries, GPU device creation and fallback, RAW/DNG/HEIC handling, ICC/color management, edits, exports, camera metadata, albums, undo, watermark and performance. Do not shrink out reflection-loaded/native runtime features.
5. **Branding:** Preserve byte-for-byte `assets/lightcraft/lc-user-approved.png` SHA-256 `8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4`, approved 70%-tile adaptive icon layout, and native application-header branding.
6. **Testing isolation:** A disposable-key, release-optimized ARM64 test APK should use `com.artcraft.lightcraft.test` if technically practical, avoiding accidental replacement of the installed stable `com.artcraft.lightcraft`. Verify package, `versionName=0.18.0-android.1`, ABI, launcher Activity, certificate fingerprint and hash, and functional parity. No permanent signing, production key access, release publication or automatic install.

## Required next gates

- **Source gate:** Selectively adapt upstream v0.18 to the protected published Android features, preserving old code or equivalent behavior; add specific fail-closed regression tests and review baseline device-approval gap.
- **Pre-build gate:** Static API/SAF/updater contract, compile feasibility and feature-regression checks must pass. Leave `android_api_port_complete=false` until this is *actually* true. Do not change a JSON flag to manufacture success.
- **Single optimized build gate:** One necessary cached release-style `arm64-v8a` build signed with a disposable test key, after source verification. Compare APK size with the equivalent published baseline; old optimized preview is 72,322,038 bytes, not a debug-build comparator.
- **Device gate:** Stop on downloadable test APK. Obtain physical HONOR MagicPad 4 editing/import/export, icon/menu, update, keyboard/ESC, touch/trackpad, fonts, GPU, media and performance feedback.
- **Production gates:** User's **device-test approval**, **permanent-signing authorization**, and **publication authorization** are three separate permissions; none is inferred from an earlier step.

**Do not call the read-only preflight artifact an APK, claim owner approval for an untested published preview, or treat a successful CI status as Android parity.**
