# LightCraft Android source review — 22 October 2026

This extends existing draft PR16 and its exact approved Lc; it does not create a replacement shell, production key, versionCode reservation or APK.

## Immutable inputs

- Official stable [v0.11.0](https://github.com/storytold/lightcraft/releases/tag/v0.11.0) resolves directly to commit ec0cda9a6f320e3b32f659f16718f7bce6c3f12f.
- Mostafa reference ac54d62d9d2d6f663295a4afd8972a7a3e79f9af: reuse its LightCraft-specific SAF_RECIPES entry in lib/build-common.sh. There is no separate adapters/lightcraft directory at that reference. The existing recipe creates LightcraftApp with Session::new().with_fs() and platform Services, worker-thread asynchronous picker, file/folder imports and staged export commit.
- Second required reference: morte android-port 71c919b768c6d70bc8231b92e3de6a81fb949996. Reviewed apps/photocraft-android/src/layout.rs and NOTICE. Its compact_layout/menu hooks are PhotoCraft-specific, so do not transplant that host or its command defaults. No code/artwork from it is copied in this preflight.
- Exact original Lc: assets/lightcraft/lc-user-approved.png, SHA256 8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4.
- source-lock.json records SHA256 of reviewed source APIs, notices and builder generator. The preflight rejects wrong/dirty tracked checkouts and changed reviewed files. It is a source audit, not a Rust compiler or APK test.

## API and engine preservation

Official UI exposes LightcraftApp::new(Session, Services), logic(&Context) and ui(&mut Ui); Services contains picker, write and write_shared. Use egui 0.36 root-Ui APIs. Preserve RAW decoder, non-destructive DevelopSettings, colour/ICC processing, photo catalog/sidecars and actual export engines. No engine file is changed here.

The source has text watermarks (docs/vertical-watermarks.md and crates/engine/src/export.rs), so font support cannot be dismissed as universally inapplicable. Existing grapheme shaping, vertical substitutions and font fallback must survive font integration. UI font installation alone would not prove export watermark font support.

Official shortcuts.rs already implements app.setShortcut, saved ui.json keymap and conflict handling. Integrate hardware modifiers/IME with these commands, not Photoshop defaults. The reference persists UiState, but Android dispatch, focus-loss reset and actual saved shortcuts need compiler/device evidence.

Desktop apps/lightcraft/src/window_gpu.rs implements a renderer fallback chain. That desktop code is not proof of Android GPU initialization. Distinguish UI renderer, processing engine and software fallback in diagnostics; no pressure/tilt/palm rejection or GPU performance is claimed.

## Per-app combined checklist

| Requirement | State and next evidence |
| --- | --- |
| Exact Lc artwork | Original staged and hash-gated; APK legacy/adaptive resources awaiting build verification |
| Official source/reference provenance | Implemented preflight; five local rejection/acceptance tests pass; CI result pending |
| SAF files/export | Existing app-specific reference implementation reviewed; Android compile, cancellation/URI permissions, RAW import and export payload fidelity awaiting validation |
| Native TTF/OTF and nonfloating UI | Pending implementation; must connect to actual watermark font selection/export as applicable |
| Persisted bounded shared folders/refresh | Pending implementation; apply only to actual font/text workflow with bounded SAF reads |
| Manual updater/saved optional startup | Pending implementation; require correct app channel, useful errors and verified monotonic metadata |
| Physical/customizable keyboard and IME | Upstream customization exists; Android bridge, independent modifiers, focus reset/IME validation pending |
| Optional docked Shortcut Pad | Pending app-command review, persisted visibility and modal/text-entry guards |
| Tablet/touch/mouse/trackpad/stylus | Pending Android layout/input review and real device checks; advanced stylus unclaimed |
| GPU diagnostics/fallback | Pending Android adapter/processing integration; desktop fallback is reference only |
| RAW/colour/export regression | Engine untouched; representative RAW/ICC/sidecar/export regression and device acceptance pending |
| Production identity/version/release | Blocked at later signing stage: no LightCraft certificate/installed-code record found in accessible signing repositories/releases; audit before key setup |

## Licensing and validation boundary

Mostafa is MIT. LightCraft NOTICE declares MIT OR Apache-2.0 with separate notices: Inter/craft fonts OFL, spectral-data attribution including CC-BY-4.0, and Apache-only SAM code. AI weights are not bundled; keep download/license choices unchanged. Preserve NOTICE, LICENSE-MIT, LICENSE-APACHE and relevant third-party/font attribution when packaging. morte NOTICE likewise has per-component font/icon exceptions. The Lc is user-approved artwork; no upstream trademark asset is substituted.

The source-preflight workflow has read-only contents permission, no secrets/signing, no native heavy candidate, no default-branch schedule and no publication. VersionName intent is 0.11.0-android.1 only; no provisional code is treated as a production reservation.

Next: reuse the pinned generated LightCraft recipe in a bounded ARM64 source/Java check, reconcile current API fields and Android JNI/egui versions, then add app-appropriate enhancements without engine removal. Coordinate with the existing FilmCraft candidate and VectorCraft signing integration before starting another heavy APK.
