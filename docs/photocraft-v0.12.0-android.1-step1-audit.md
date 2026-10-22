# PhotoCraft v0.12.0-android.1 — Step 1 source and Android compatibility audit

**Status: AUDIT / DRAFT ONLY. No v0.12.0 source has been merged or built.**

## Provenance and isolation

- Official stable source: [storytold/photocraft v0.12.0](https://github.com/storytold/photocraft/releases/tag/v0.12.0).
- Exact official tag commit (GitHub refs/tags/v0.12.0, lightweight tag): `6a2d027ee2e7ca12afd248544ed2262b0fa078dd`.
- Android reference: `MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
- This development branch starts at existing PhotoCraft Android builder baseline `KosmosSG/artcraft-android@353a8523d7d9c41d52ced6575d543f1a2aabba4e` (`photocraft-v0.10.5-development`). This preserves the existing builder and adapter for inspection; it is **not** evidence that the new upstream source has been ported.
- Existing draft PRs [#3](https://github.com/KosmosSG/artcraft-android/pull/3) and [#4](https://github.com/KosmosSG/artcraft-android/pull/4) are separate and must not be silently merged. No duplicate APK build or release.

## Verified source / adapter facts

- Official v0.12.0 root Cargo workspace: version `0.12.0`, Rust `1.95`, edition `2024`, license `MIT OR Apache-2.0`, `eframe`/`egui` `0.36`. Rust 1.95 availability on the selected runner must be verified.
- Existing Android adapter `adapters/photocraft/Cargo.toml`: package `com.artcraft.photocraft`, ARM64 target `aarch64-linux-android`, min SDK 28, target SDK 35, custom `PhotoCraftActivity`, launcher intent, JNI 0.22. Do not change identity.
- Existing `adapters/photocraft/src/lib.rs`: PhotoCraft engine/UI/text/codec integration, JNI Android file open/save, custom TTF/OTF font registration, reload from app-private `custom-fonts`, and Android system-font bridge. Adapter source also references update handling; behavior must be regression-tested rather than assumed.
- Existing `templates/android`: `SafActivity.java`, `saf_bridge.rs`, `ime_bridge.rs`, `system_fonts.rs`. Check Java SAF picker and persisted shared-folder grants, IME, physical-key modifiers, and updater UI on device.
- Existing `lib/build-common.sh` supports `-appicon` and copies a custom adapter. **Critical:** its ordinary upstream checkout uses `git clone --depth 1`; do not assume this pins the official tag/commit. Add a verified pinned-checkout step in a later, reviewable change before building.
- Official v0.12.0 release describes changes to UI, text warp, selections, large documents, PSD/PSB, and graphics; adapter API compatibility with `photocraft-ui-egui`, `photocraft-engine`, `photocraft-text`, `photocraft-doc`, `photocraft-codecs`, and `photocraft-io` is **not yet established**. Compare exported APIs and compile before any promotion.

## Feature-preservation and release gates (not yet passed)

| Requirement | Existing baseline / evidence | v0.12.0 status |
| --- | --- | --- |
| Package and signing identity | `com.artcraft.photocraft`; private signing workflow already exists | Must verify original signer SHA-256 and package |
| TTF/OTF import and persistence | Adapter has `register_custom_font` and `load_custom_fonts` | Needs API and runtime test |
| Shared SAF font folder | Android SAF bridge/templates and prior published Android release | Needs folder grant/refresh regression |
| Open/save and content URI persistence | Android file bridge and SAF Java | Needs round-trip tests |
| GPU diagnostics / CPU fallback | Prior Android release claims feature; not proven by this adapter inspection | Must inspect graphics integration and test |
| Help / Check for Updates | Existing adapter/update integration and prior release | Must test versionCode ordering and no silent install |
| Physical keyboard, custom shortcuts, IME | Existing bridge; not all requested enhancements proven shipped | Audit/port only applicable changes |
| Tablet gestures, stylus, shortcut dock | Requested enhancements; not confirmed in current release | Scope individually, avoid claiming complete |
| Approved glass Pc launcher | Exact original PNG expected at `assets/photocraft/launcher-pc.png`, SHA-256 `1a6495c214ae4536b432a34feff9b7001b612d4df1e79bf784b00d5b393f8a9b` | Not committed; reject substitution |
| ARM64 APK | Target `aarch64-linux-android` | Not built |
| VersionName | Proposed `0.12.0-android.1` | Not applied |
| VersionCode | Must exceed **all** previously installed/published signed APKs (not just v0.10.3); most recent published `0.10.0-android.2` notes code `16790001` | Reserve only after verifying latest installed/signed codes |
| Signing key | Private repo `KosmosSG/photocraft-signing-private`; original key and encrypted backup must remain untouched | No signing action |
| Publishing | Explicitly forbidden at this stage | Disabled |

## Step 2, subject to review

1. Compare pinned v0.12.0 public APIs against the Android adapter, generated launcher, Java activity, fonts and WGPU fallback; record API differences and licensing/third-party dependencies.
2. Add a **fail-closed** pinned upstream checkout using exact commit above, not floating main, without modifying original source or private signing repository.
3. Port necessary changes on this branch with focused CI checks; test source provenance, JNI/Java compilation, Rust ARM64, font import, SAF open/save, version metadata and icon SHA.
4. Only after CI, prepare an isolated **unsigned or ephemeral-key** candidate if authorized; do not run production signing or publish. Preserve the permanent signing identity for a separately reviewed private signed build.
5. Review and test on HONOR MagicPad 4 MagicOS 10 before promotion.

**Safety:** This Step 1 change is documentation only. No upstream merge, APK build, signing, release, auto-merge, or auto-publishing.
