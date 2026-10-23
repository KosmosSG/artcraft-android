# PDFCraft Android — isolated v0.10.1 candidate audit

**Status:** DRAFT / REVIEW ONLY. No released PDFCraft Android APK, no permanent PDFCraft signing identity, and no device verification are established by this document.

## Provenance / fixed inputs

- Official source: [storytold/pdfcraft](https://github.com/storytold/pdfcraft), latest stable GitHub release inspected 2026-10-22: [v0.10.1](https://github.com/storytold/pdfcraft/releases/tag/v0.10.1).
- Resolved lightweight tag `refs/tags/v0.10.1` -> **`b77d57000c22c760f731206f6cf14486d149de72`**. Candidate jobs MUST verify tag resolution and fail if it changes; never build arbitrary `main`.
- Android reference reviewed: [MostafaXS1/artcraft-android@ac54d62d](https://github.com/MostafaXS1/artcraft-android/tree/ac54d62d9d2d6f663295a4afd8972a7a3e79f9af). Prefer the existing improvements already present in this repository over replacing them from the reference.
- Base suite branch: `main` at creation `7b46f87aba112fff93380e01379045733f09f8b3`.
- Upstream Rust requirement: **1.95+**, edition 2024, workspace v0.10.1; `pdfcraft-ui-egui::PdfCraftApp::new()` is the correct entry point. Existing `lib/build-common.sh` has a specific PDFCraft generator recipe that uses `rfd::artcraft_saf`; it stages Android-native document SAF via `PdfCraftActivity`, processes incoming documents, and uses an Android-specific arboard fallback. These are **source-level findings, not verified on-device behavior**.

## Licence and branding review required for distribution

- Workspace is **MIT OR Apache-2.0**. Preserve upstream copyright/attribution/NOTICE and relevant third-party license texts.
- **Important:** `docs/brand/LICENSE-brand.txt` explicitly restricts ArtCraft names/marks in modified forks. The requested independent PdfC icon is supplied by the user, but a public modified build must not incorrectly imply ArtCraft endorsement. Check visible in-app branding and release text before any distribution.
- No PDFCraft signing repository, PDFCraft-specific existing GitHub workflow, prior release asset, PDFCraft PR or PDFCraft branch was found in the currently accessible repositories on 2026-10-22. This is **not proof** that no APK was privately installed or signed outside accessible GitHub.

## Package, version and signing HOLD points

- Proposed package id from the suite generator: `com.artcraft.pdfcraft`. Inspect the APK and confirm no existing installed identity before permanent signing; **never change an existing identity silently**.
- Proposed first candidate display version `0.10.1-android.1`, file `pdfcraft-0.10.1-android.1.apk`. Version code is **NOT RESERVED** until earlier signed/installed/public builds have been ruled out. Explicit AndroidManifest verification required; renaming an APK is not versioning.
- Candidate may only be ephemeral-key signed; its certificate **must not be reused** for public release or claimed as an update to installed copies.
- Existing `build-common.sh` generates `keys/artcraft-builder.jks` when absent, and does not currently implement app-isolated release keystore, suite versionName/versionCode overrides, or signed-payload equivalence. Its generated key on a disposable GitHub runner is ephemeral only. Do not commit key/password; do not route it into future permanent PDFCraft signing.
- A **new PDFCraft-only permanent signing identity**, encrypted backup, SHA-256 certificate fingerprint and versionCode ledger must be created *only if* the preflight definitively finds no earlier PDFCraft signing identity. Never borrow PhotoCraft/VectorCraft/DesignCraft keys.

## Uploaded icon

- The user approved a glossy red rounded-square launcher graphic with the **exact capitalisation `PdfC`**, white/red liquid-glass letters, and solid dark-red interior. Original supplied 1254x1254 RGBA PNG SHA-256: `8f83a162200c85965c85892229c2b5c02fd69c28402f75be8a13c119497ac63f`.
- Proper legacy and adaptive Android launcher assets must be generated **from this uploaded artwork**. Verify image remains visible, appropriately padded within adaptive icon safe area, has no extraneous black border, and is *actually packaged* into the test APK. An icon preview alone does not satisfy this.

## Functional gates before promoting or publishing

1. Preserve all PDF document content. Regression files: embedded fonts and RTL/CJK, incremental saves, existing annotations, AcroForms/XFA, encrypted PDFs, external links, signatures, and non-destructive save/cancel paths. Never promise unlimited PDF editing or original signatures surviving a document-changing save.
2. Ensure Android `ACTION_VIEW`/send, document SAF open/save/save-as/export, persistent URI/filename mapping, cancellation and duplicate-name safety, clean close/reopen. Confirm PDF MIME filters.
3. Check genuine viewer/render/search/zoom/text selection/copy, e-ink/IME/physical-keyboard chord behavior, mouse-wheel/stylus events and tablet layouts. Only expose controls the real `pdfcraft_engine::commands::COMMANDS` registry supports; evaluate user-editable shortcuts and an optional docked touch Shortcut Pad.
4. Assess import of TTF/OTF for the **editing tools that support custom fonts** without a floating font manager. Preserve embedded original fonts.
5. Inspect PDFCraft-specific GPU diagnostics, fallbacks and render errors; **do not invent GPU detection**. Check native Android `PrintManager` availability separately from upstream desktop printing.
6. Implement explicit check-for-updates feedback and persist startup preference only after separate updater metadata and compatibility checks.
7. Build-only CI is not enough: inspect APK `versionName`, monotonically reserved `versionCode`, `arm64-v8a` only, expected package/activity, SAF Java bridge, icon resources, signing certificate, SHA-256, and update payload hash identity. Mark hardware behavior **untested** until user tests on HONOR MagicPad 4 / MagicOS 10.

## Isolation policy

- All PDFCraft work stays on `pdfcraft-v0.10.1-android1-candidate` (and later PDFCraft-scoped review branches).
- No changes to other apps' workflows, branches, package IDs, release tags or keys.
- Do not merge PRs, modify `main`, enable `schedule` on `main`, or publish any signed release until release checks pass.
