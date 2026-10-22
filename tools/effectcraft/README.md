# EffectCraft Android candidate — release-gated review

This is an **isolated draft**. Do not merge, tag, publish, activate any schedule, or run permanent signing from this review branch. No other ArtCraft app's adapter, workflow, branch or signing material is changed.

## Audited source and proposed identity

- Official stable upstream `storytold/effectcraft` release: [v0.14.0](https://github.com/storytold/effectcraft/releases/tag/v0.14.0), announced 2026-10-21.
- Verified immutable tag target: `26b40199b72121aa7f4e55a63718e1b4dd48a859`.
- Reference Android builder: `MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
- Actual suite starting point: `KosmosSG/artcraft-android@7b46f87aba112fff93380e01379045733f09f8b3` (do not replace its enhancements with the reference repository).
- Upstream workspace version: `0.13.0`, Rust 1.95+, edition 2024, license `MIT OR Apache-2.0`. Review NOTICE/ATTRIBUTION and transitive licensing before distribution.
- Target: MagicOS 10, ARM64 / `arm64-v8a`.
- **Proposed, not yet emitted in an APK**: versionName `0.14.0-android.1`; asset `EffectCraft-v0.14.0-arm64-release.apk`; package `com.artcraft.effectcraft`, pending any previously installed identity check.
- **VersionCode is deliberately unassigned**. Compare with all previous signed, installed and published EffectCraft APKs *before* reserving a value.
- EffectCraft's permanent certificate and encrypted keystore backup could **not** be established by read-only repository inspection; no existing dedicated signing repository appeared in the linked repository list. This is not proof no prior keystore exists outside GitHub. Do not create or rotate a production key until verified.
- Candidate APKs must be ephemeral-key signed, labeled **not upgrade-compatible**, and kept as private CI artifacts only. **No release** until a separately verified permanent signing flow, immutable payload comparison, and a recorded SHA-256 + certificate fingerprint are checked.

## Compatibility findings (reviewed, not yet implemented by this PR)

- Upstream `crates/ui-egui/src/lib.rs` exposes `EffectcraftApp::new(Session)`, `Hooks::file_dialog_async`, `FileDialog::Open/OpenProject/Save/Folder`, and optional audio hooks.
- `crates/host/src/lib.rs` exposes a wired media/import/export `session()`. The generic builder's EffectCraft recipe currently constructs `EffectcraftApp::new(Session::new())`: **review whether this omits host importer/exporter, expressions and media support before compiling**. Do not silently drop render/export features to pass CI.
- The existing builder `lib/build-common.sh` contains an EffectCraft-specific SAF bridge, async picker, document-opening intent path, preferences recipe and audio module support. Confirm those hooks against this *pinned* release.
- The builder's generic keystore `keys/artcraft-builder.jks` and upstream `<app>-<version>.apk` naming **do not yet satisfy** the permanent-signing and `-android.1` distribution policy.
- Upstream `effectcraft-engine::Session` has explicit `accel` and GPU reason fields, and EffectCraft's UI already tracks GPU initialization/failures and CPU viewer paths. Diagnostics must report the *actual* backend, never infer acceleration from hardware names.
- EffectCraft includes command/keymap infrastructure and a Shortcuts dialog; reuse it for physical keys, customization, optional docked Shortcut Pad. No floating font window.
- Evaluate native TTF/OTF import into text engine's font locations; SAF folder permissions vs app-private staging; renderer, playback, animation, queue and export behavior; GPU/Auto/CPU fallback; storage/network access and update-check preference.
- Device testing is pending; compilation alone cannot demonstrate functionality.

## Approved launcher artwork

Use the exact **Ec** (capital E, lowercase c) user-supplied artwork for **EffectCraft only**, SHA-256
`376a9b60f3ca15174a8a4e07563d5f4402a03011bc86e56395134f3f8f88661b` (original 1254×1254 RGBA PNG). Density assets have been prepared from the original outside GitHub; **binary artwork is not included in this PR and no icon has been verified inside an APK**. Later integration must add the approved PNG/mipmap files, inspect Android Manifest launcher references, and inspect the APK asset hashes. Never substitute another suite app's icon.

## Gate sequence

1. Pin sources and preserve existing app/suite enhancements, licences, and package identity.
2. Land an **isolated non-publishing temporary-key candidate workflow** only once Android versionName, strictly increasing versionCode and the immutable source pin are applied; it must upload artifacts privately, no GitHub Release or secrets.
3. Confirm manifest package, versionName/versionCode, `arm64-v8a` only, SAF/activity, Ec launcher, file associations, true GPU reporting, render/export and signed APK hash/cert.
4. Establish the previous signed/installed certificate and versionCode. If no permanent EffectCraft identity ever existed, plan a **dedicated EffectCraft-only** key and encrypted backup separately.
5. Separately verify permanent-key signing does **not** rebuild or change the unsigned payload. Gate public releases on all checks and keep upstream update detection review-only until proven safe.

## Repository safety

No push to main; no auto-merge; no schedule activated; no other app workflow edits; no signing material or secrets copied; no APK published by this review.

## v0.14.0 candidate status

Upstream source is now pinned to the October 21 official stable v0.14.0. The separately guarded candidate workflow is intentionally non-publishing and produces only an ephemeral-key Actions artifact, if compilation and integrity checks succeed. `effectcraft_host::session()` is required to preserve import/export and expression services. User-approved Ec artwork, Android SAF font picker UI, in-app updater UI, permanent dedicated key and encrypted backup, signed update continuity and tablet tests remain pending. Do not distribute a temporary-key build.
