# LightCraft v0.20.0 → Android: protected integration review (10 Nov 2026)

## Immutable source references
- Published Android baseline: `lightcraft-v0.18.0-android.1`, commit `1cf18815195c640b28dfd50410ae112a8975c8b4`.
- Existing integration branch: `integration/lightcraft-upstream-20261110`; first commit only added `configs/upstream/integration-20261110-lightcraft.json`.
- Official source: `storytold/lightcraft` `v0.20.0`, commit `192ff72923c39e6623f2c7ff67ab3a119deb8071` (verified exact GitHub tag).
- Official upstream workspace: Rust 1.95, egui/eframe/egui_extras 0.37, wgpu 30; do not assume legacy builder compatibility.
- Upstream v0.18.0 to v0.20.0 spans 316 commits. Do not wholesale replace Android adapters, patches, manifest, launcher, fonts, updater or SAF.

## Feature-by-feature upstream review and implementation requirements
1. **Lightroom masks**: consider upstream PR #3862 (inverted Lightroom mask import); adapt catalog/develop/engine code; test inverted vs non-inverted and catalog recovery.
2. **RAW**: upstream PR #3916 withdraws compressed ORF support pending provenance. Preserve upstream's intentional restriction; do not silently re-enable unsafe decoder. Check Fujifilm DNG Kelvin fixes from PR #3887.
3. **Film grain V4**: upstream PR #3630 introduces resolution-independent crystal-layer grain. Review film/pipeline/engine shaders and ensure identical preview/export without introducing GPU allocation/thermal regressions. Upstream claims no GPU cost; verify on Adreno rather than assume.
4. **Updater**: upstream PRs #3995/#3996 introduce craft-update install-on-exit behavior. **Do not replace Android GitHub Releases updater** with desktop installer behavior. Android updater, startup checks, package verification and user-controlled install must remain Android specific.
5. **UI**: upstream fixes selected-photo count (#3833). Preserve Android Lc icon/menu, trackpad hover, Appearance, keyboard/ESC and SAF hooks.
6. **Graphics**: retain Vulkan-first and safe fallback, GPU/resize/load error logging, lazy resources, frame pacing based on reported display rates; cap to current device capabilities with conservative thermal fallback. A 165 Hz display does **not** establish 165 FPS throughput. Profile median and p95 frame time and thermal throttling.

## Essential Android compatibility blockers
- `.github/workflows/lightcraft-v018-arm64-test.yml` is **v0.18-only**, hard-pins upstream SHA `32d569...`, edits `version = "0.18.0"`, expects old paths, and patches a specific egui/winit launcher. **Never run it as a v0.20 candidate**.
- `tools/lightcraft/patch_v018_android.py` is intentionally fail-closed to v0.18; port it into a distinct v0.20 patch after inspecting exact source anchors. Don't weaken the v0.18 provenance guard.
- Existing `tools/lightcraft/source-lock.json` still contains an older historical baseline; for this integration the authoritative baseline is the published v0.18.0-android.1 tag.
- Audit every match on `winit::event::WindowEvent`, including `ImeResetCompleted` and custom fork variants; preserve upstream's IME semantics. Test Ctrl+Q re-entry, soft keyboard, physical-key focus, and cold start.
- Distinguish package `com.artcraft.lightcraft.test` from released `com.artcraft.lightcraft`; use only a disposable keystore. Do not copy/access production signing secrets.
- Preserve the exact owner-approved launcher assets and icon checksums. Ensure the published production APK is untouched.
- Stay within LightCraft scope. No changes to PhotoCraft, WordCraft, other apps, releases, or default-branch production files.

## Required implementation sequence and stop gates
1. Freeze published baseline commit and compare full upstream v0.18..v0.20 diffs, including changed transitive APIs and licenses; record intended cherry-picks/adaptations.
2. Create **v0.20-specific** provenance verifier and source patch, and unit-test fail-closed anchors on the exact upstream commit.
3. Update **LightCraft-only** builder/template for egui 0.37, wgpu 30 and the actual pinned winit fork; validate Android event exhaustiveness including `ImeResetCompleted`.
4. Run host/source Rust test suite and integration regression checks before costly ARM64 CI.
5. Use a **single** cached, non-publishing, manual v0.20 ARM64 CI job after checks pass; target `com.artcraft.lightcraft.test`; sign with a newly generated disposable key; upload APK plus SHA256, package badging, cert fingerprint and toolchain report. Optimize size without stripping needed assets.
6. Check `apksigner`, `aapt`, ARM64 native libraries, distinct certificate from published SHA-256 `B2:C8:94:BE:26:AF:D5:41:ED:99:15:AA:38:61:B8:2B:04:0F:93:8D:FC:D8:4D:85:3F:EA:ED:8C:E2:9B:F2:F4`. Never claim validation until evidence exists.
7. Device test: 10 cold starts, no black screens; 10 Ctrl+Q relaunches; app menu/hover; keyboard and D/C/S; SAF save/open; fonts shared/refresh; updater; RAW/import/edit/export + mask/grain; pan/pinch with no selection boxes; Vulkan stability and thermal frame pacing.
8. Stop at **TEMP-SIGNED TEST APK**. Do not merge, permanently sign, tag or publish until explicit user approval.

## Current state
Source review and baseline ancestry **verified**. v0.20 source migration, Rust compile, Android build, signature, APK artifact and HONOR MagicPad 4 device test **not performed / not verified**. This document is a review gate, not an integration or release claim.
