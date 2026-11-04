# PDFCraft v0.18.0 — isolated Android upstream integration (TEST ONLY)

**Status:** Owner-authorized development through temporary-signed ARM64 test APK only. NO permanent signing, merging to production, public prerelease, or publication.

## Protected baseline and inheritance
- Latest published approved PDFCraft stable: `pdfcraft-v0.12.1-android.3`, source commit `ba604057f77eb0ae45dac85914280121d0e9eb12`, package `com.artcraft.pdfcraft`; keep APK, tag, signer, and data unchanged.
- Preserve the Android integration inherited from `integration/pdfcraft-v017-arm64-candidate-20261102` (draft PR #115; 2026-11-03 passing Actions run 41596440893). Experimental integration is not a replacement for the protected published release.
- Official upstream `storytold/pdfcraft` `v0.18.0`, immutable tag commit `3936f93a1479366a951206fc6d3094680fe2d3dc` (published 2026-11-03).
- Use official source + existing guarded Android-only overlay. Never replace it wholesale with a reference fork.

## Compatibility and feature preservation
- Compared to v0.17: official `crates/ui-egui/src/menus.rs`, `platform/updates.rs`, `app/keys.rs`, `dialogs/prompts.rs` and `crates/engine/src/text_fonts.rs` are source-identical at v0.18.0.
- `crates/ui-egui/src/app.rs` and `canvas.rs` changed upstream. Patch exact anchors and idempotence must pass; do not suppress API incompatibilities.
- Rust 1.95+, egui 0.37 and immutable official winit/egui pins are unchanged from v0.17 (source checked).
- Retain SAF open/save/export, private recovery, font import/refresh and 5,000-file/4 GiB recursive scans, Help updates, approved red PDFc icon, light/dark Android toolbar, H/V/Ctrl/Escape/D/C/S, touch/trackpad gestures, and wgpu diagnostics.
- Inspect v0.18 annotations, page management, raster rendering, menu changes and recent-files interaction with Android. Do not claim undocumented PDF hardware functionality or save fidelity passed without device verification.
- Candidate version `0.18.0-android.1`, versionCode `16781825`, package `com.artcraft.pdfcraft`, disposable-only signing. It **will not update a production-signed stable installation in place**; preserve and back up existing data.
- Candidate workflow intentionally uses a name not allowlisted in the existing automatic test pre-release publisher, grants `contents: read`, and only uploads private Actions artifacts. No release permission or production secrets.

## Gates
1. CI verifies immutable upstream tag SHA, source origin, workspace version and guarded adapter tests including patch idempotence, IME/gesture/keyboard and PDF read/write.
2. CI verifies ARM64-only APK, identity/version, launcher icons, ephemeral signature, ZIP alignment, file bridge, SHA-256.
3. User tests on HONOR MagicPad 4: PDF editing/save/export, SAF round-trip, recovery, imported/system/recursive fonts, keyboard shortcuts (H/V, Ctrl+O/S/W/Z, Escape, D/C/S), two-finger touch and trackpad, GPU diagnostics, adaptive icon and update checker.
4. STOP for explicit device-test confirmation, separate permanent-signing authorization, and separate publication authorization. Do not merge or publish automatically.
