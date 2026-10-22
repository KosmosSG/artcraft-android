# VectorCraft Android 0.14.0-android.2 review

Reviewed 23 October 2026 (Malaysia time). This report distinguishes source inspection and automated checks from device tests.

## Source and compatibility

- Official stable release: storytold/vectorcraft v0.14.0, commit `ad0566943ab9741e6356bbc9b53c3cc09895068d`. The existing Android branch already targeted this release; no newer stable upstream integration was necessary.
- Existing enhancement baseline: `efb74bdac8932c67d3c75f2730efdaea4aa27741`.
- Application adapter built for this candidate: `18f81954ba0aeb47beaa639064bc6254d83c1164`.
- Builder: MostafaXS1/artcraft-android `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
- Package remains `com.artcraft.vectorcraft`; candidate versionCode 16780802 follows the previously signed baseline 16780801.
- Permanent certificate SHA256: `7fc384231187a50f7ac3d6fe45e1f0c5b728e195ef24e783b087dce0d3af93f5`.
- The production pipeline lives in the private VectorCraft signing repository. It restores the existing AES-256-GCM/scrypt `.enc` envelope and does not generate a replacement identity. The old public workflow's direct-base64-secret signer is not the active production path.

## Existing features preserved

| Area | Evidence / limits |
| --- | --- |
| Documents | Existing SAF asynchronous open/save bridge, intent opening, staged paths and saved URI mappings retained. Physical storage-provider testing pending. |
| Fonts | Existing TTF/OTF import, persisted read-only shared-folder grants, app font directory and `text.rescanFonts` retained. |
| Shortcuts | Upstream tool catalog supplies V/A/P/T/M/L/B/R/S/H/Z; command shortcuts and conflict editor remain upstream-owned. Both VectorCraft Defaults and Classic Defaults currently use the registry defaults. Saved user overrides are retained. |
| Android modifiers | Existing Ctrl-to-command mapping, text suppression for Ctrl chords and focus-loss reset retained. Bluetooth/USB behavior remains untested here. |
| Tablet UI | Existing optional undo/redo/shortcut dock, display configuration handling, IME and fullscreen shell retained. No new stylus-pressure implementation or landscape benchmark is claimed. |
| Updates | Filters stable `vectorcraft-v` tags and VectorCraft APK assets, compares version/revision and opens the release page. It does not use the repository global latest endpoint. It currently scans the first 100 releases, not an unlimited history. |
| Rendering | Official document renderer explicitly uses `vello_cpu`; the Android host requests eframe/wgpu for UI presentation. Adapter diagnostics query the live wgpu adapter if exposed. Neither Adreno execution nor GPU canvas rasterization has been measured on the target tablet. |

## Changes in this candidate

- Compare font SHA256 content before importing an identical font again, including files saved under legacy UUID filenames. Existing imports are not renamed or removed.
- Refuse replacement of the shared cache after an incomplete, unreadable or limit-exceeding scan, preserving the old cache.
- Add a persistent opt-in startup-update preference, default off, and show available-update feedback.
- Explain the existing Classic Defaults shortcut preset in Android Tools without overwriting mappings.
- Preserve the exact approved Vc icon and the existing launcher safe-area preparation.

## Automated verification

- 13 existing Python verification/feature-guard tests passed locally and in GitHub Actions.
- Android Java bridge compiled against Android API 35.
- Host JVM checks passed: legacy filename recognition, filename-independent digest, distinct content, missing directory, existing-file preservation.
- ARM64 Rust adapter check passed: https://github.com/KosmosSG/artcraft-android/actions/runs/39828124149
- Production build/signing run: https://github.com/KosmosSG/vectorcraft-signing-private/actions/runs/39828277823 (private; still running when this report was written).
- No physical-device tests, end-to-end vector file round trips or performance benchmarks were run in this session.

## Target-device acceptance checklist

1. Install over the previous same-certificate build without uninstalling; confirm existing drawings, fonts and settings remain.
2. Import Montserrat TTF/OTF twice, then use it in text; verify the second import reports that it is already available.
3. Select and refresh the shared font folder. Revoke provider access and confirm the previous fonts remain usable.
4. Save/reopen a native document; import/export representative SVG, PDF and PNG documents using actual supported menus; compare geometry, text, fills and strokes.
5. Test requested tool keys and Ctrl copy/cut/paste, undo/redo, save/save-as, select-all, grouping and zoom with a physical keyboard; ensure typing in text fields does not switch tools.
6. Edit a shortcut, exercise conflict feedback, restart and verify persistence.
7. Test touch/stylus selection, path handles, pan/zoom, landscape/portrait, mouse input and suspend/resume.
8. Open Android Tools > Check for VectorCraft Updates. Enable/disable startup checking and verify persistence; test offline behavior.
9. Capture Android Tools graphics diagnostics. Record actual adapter/backend rather than inferring GPU use from the tablet model.

## Outstanding scope

Help-menu integration (updates currently live in Android Tools), direct in-app APK downloading/installer handoff, release-history pagination, broad font deduplication across both shared and imported caches, measured GPU canvas acceleration, large-document performance tuning and new stylus-specific behavior remain outstanding. Core vector editing comes from the pinned upstream; no additional format or editing-tool support is claimed.
