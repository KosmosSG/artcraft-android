# PDFCraft Android — PhotoCraft parity and acceptance gates

**Scope:** isolated PDFCraft candidate PR; only build the official `storytold/pdfcraft` v0.10.1 (SHA `b77d57000c22c760f731206f6cf14486d149de72`); never alter PhotoCraft or other app branches.

## Reviewed reference: working PhotoCraft features

The published PhotoCraft `photocraft-v0.10.0-android.2` release and the `photocraft-android2-release-source` adapter demonstrate Android SAF document pickers, TTF/OTF import, persistent shared `ArtCraft-Fonts` folder selection/refresh, automatic restoration, app-level update-check feedback and a startup-check preference. PDFCraft has different internal document-font rules; do not copy PhotoCraft's `photocraft_text` API or its floating Custom Fonts window.

## Candidate features implemented in PDFCraft-only source

| Feature | Source integration | Acceptance requirement |
|---|---|---|
| SAF single-font import | Dedicated Activity ACTION_OPEN_DOCUMENT; TTF/OTF, max 16 MiB; content-addressed cache | Test picker success/cancel, invalid fonts, filenames, offline behavior |
| Shared font folder | ACTION_OPEN_DOCUMENT_TREE with read-only persistable URI; re-open stored URI and bounded recursive scan (up to 200 font files / 1,000 folders) | Select same Android `ArtCraft-Fonts` folder as PhotoCraft, refresh, restart, revoked grant, nested directories |
| PDF-specific font validation | Guarded Android source integration adds private `PDFCRAFT_ANDROID_FONT_DIR` to PDFCraft `text_fonts::installed_directories()`; original `pdfcraft-fonts::embedding::validate_document_input` remains the gate | Verify only eligible document fonts appear in supported editing tools, and that text rendering/embedded fonts and existing PDFs are unchanged |
| No floating font manager | Font buttons in a collapsible, docked bottom panel | Test touch, landscape/portrait, mouse, IME, usable document viewport |
| Manual update check | Bounded HTTPS GET to publicly published `KosmosSG/artcraft-android` releases; filter `pdfcraft-v<official>-android.<revision>` with matching `pdfcraft-<official>-android.<revision>.apk` asset | Up-to-date, available, HTTP failure, no Android releases yet, correct installed version |
| Optional startup checks | Disabled by default, Android SharedPreferences boolean | Toggle and restart; never download/install automatically |
| Safe update hand-off | Explicit user action opens a verified GitHub release page only | Never claim a release is install-compatible until package/certificate/versionCode and payload checks pass |

**Note:** PhotoCraft's update checker and font-import code are reference designs; PDFCraft's implementation has separate methods and preserves upstream PDF APIs. The upstream desktop Help > Check for updates currently refers to **desktop** releases; the Android-specific action is on the PDFCraft dock until it can safely be integrated with PDFCraft's own Help menu.

## Other PhotoCraft/tablet parity requests — assessed, not yet claimed complete

- Physical keyboard modifiers and Android IME: reused current builder integration. PDFCraft has its own `pdfcraft_engine::commands::COMMANDS` and `PdfCraftApp::execute`; configure shortcuts only against real command IDs. A docked touch Shortcut Pad and persisted customizable mapping need separate validated work.
- GPU: log only actual Android renderer/backend, adapter and fallback data; desktop Linux/Windows GPU detection cannot be copied to MagicOS. No GPU acceleration improvement is claimed from this PR.
- SAF open/save/export, Android Open with/share PDF filters and font rendering: existing Android shell is retained, but complete document round trips still need device tests.
- Native printing: desktop `spool::printers` is not Android `PrintManager`; printing needs a separate adapter and tests. No claim of Android printer support.
- Annotations, form filling, incremental saves, digital signatures: preserve upstream semantics and run before/after corpus checks. A modified signed PDF may invalidate existing signatures; do not promise universal signature preservation.
- Source itself is alpha: upstream explicitly notes limits in existing text editing (CJK/RTL), XFA, professional signatures and some printing/export workflows.

## Provenance, branding, signing and promotion

The source is dual MIT/Apache-2.0. The upstream ArtCraft brand/assets licence separately restricts rebranding and public distribution of modified forks. All public messaging and in-app brand assets must be reviewed before public release.

This work remains **candidate-only**. Its GitHub runner uses a disposable signing identity. Do not distribute it as an update. Before any permanent signing, check for any old installed/signed PDFCraft APK, select a permanent PDFCraft-only key, preserve an encrypted backup, reserve monotonic versionCode across all signed builds, verify ABI/package/versionName/icon/manifest/hash, ensure signed-payload identity and complete PDF integrity testing. Do not merge or publish automatically.
