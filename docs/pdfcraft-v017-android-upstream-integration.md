# PDFCraft v0.17.0: isolated Android ARM64 upstream integration

**Status:** test-only candidate. **No merge, signing with production key, public prerelease, or release without explicit owner approval.**

## Source and upgrade boundary
- Upstream **official** `storytold/pdfcraft` release `v0.17.0`, published **2026-11-01**, immutable tag commit `7d78f3e14474b978be014715e0cc64895d77025a`.
- Inherit existing Android-only integration from `integration/pdfcraft-v015-arm64-candidate-20261029` (draft PR #87, stacked on PR #81). Do not replace it with `MostafaXS1/artcraft-android`; use that fork **as a reference only**, subject to review and attribution/licensing.
- Official v0.17.0 uses Rust >= 1.95, egui/eframe 0.37 and unchanged immutable Storytold winit/egui pins seen in v0.15. Keep the guarded IME, Android mouse, right-click, hover and wheel adapter and fail closed on any future pin change.
- The production APK remains `pdfcraft-v0.12.1-android.3`, `com.artcraft.pdfcraft`, Android versionCode `16780291`, independently signed with the owner’s PDFCraft key. The candidate versionCode `16781568` is **test-only** and does not reserve a production version.
- GitHub Actions builds with a disposable keystore. Its APK is **not an install-over update** for a production-signed app and must never be presented as a stable release.

## Android feature-preservation / reference compatibility matrix
Feature | Action and release gate
--- | ---
Autosave, SAF writes and recovery | Preserve existing SAF stage/save integration; verify periodic/autosave and crash-recovery capabilities in **PDFCraft specifically**. Do not claim recovery or SAF auto-write proven until inspected and device-tested. Test unsaved work, process kill, restart, open/save/save-as/export and cloud document providers.
Autosave and restore sessions | Review upstream v0.17.0 recent-files and session preferences; verify reopen after restart without silently overwriting documents.
Auto-build on commit | Run this isolated candidate workflow on changes to its source/adapter and on manual dispatch. No auto-publication.
Two-finger scrolling / touch / hold-for-right-click | Retain existing vendored Android winit touch+mouse/scroll/hover support. Verify two-finger scroll, long-press/right-click, trackpad scroll, stylus and keyboard focus on HONOR MagicPad 4. Add app-specific fixes only if a regression reproduces.
Mobile UI scaling | Preserve PDFCraft-specific UI, avoid changing launcher scaling before checking upstream 0.37 layouts. Test portrait, landscape, split-window and keyboard/IME.
GPU acceleration | Retain renderer's existing wgpu implementation. Run hardware inspection; do not claim GPU acceleration is available on all Vulkan/driver configurations.
Adaptive icons / adaptive cursor | Preserve approved red PdfC launcher, adaptive icon resources, native UI artwork and mouse cursor behavior; inspect the **packaged APK**. Distinguish launcher icon masking from cursor shapes.
Duplicate extension naming | Verify `sample.pdf` duplicated as `sample (1).pdf` rather than `sample.pdf (1)` for Android SAF and internal file providers before altering upstream naming code.
Existing PDFCraft extras | Preserve import/refresh shared fonts, Help menu controls, update checker pagination, D/C/S/keyboard behavior, PDF edit/save/export and original signing identity.

## Mandatory automated checks
1. Verify immutable upstream tag SHA, official source origin, workspace version and dependency pins before building.
2. Run guarded Android source adapter tests (idempotent overlay, font catalog, updater, identity/version, Help bridge).
3. Run Android IME compatibility tests, keyboard modifier tests, and upstream PDF object read/write tests.
4. Compile ARM64 only; verify exact package, test versionName and versionCode, approved launcher/adaptive icon resources, and transient signing certificate. Retain checksums and CI artifacts.
5. On any failed contract or source drift, **stop**; do not silently delete an overlay, fall back to an older upstream, reuse signing secrets, or publish.

## Manual acceptance before a production release
- Independently review official v0.15 → v0.17 upstream changes (658 commits by GitHub compare; API drift, editor/renderer and update UI are important).
- On the target HONOR MagicPad 4, open/edit/save/save-as/export real PDFs, including annotated/encrypted/signed/XFA and large/image-heavy PDFs. Check that data and signatures are not silently lost.
- Test imported/system fonts and nested font folders, right-click, two-finger scrolling, mobile scaling, escape/IME, restored sessions, icon and in-app update prompt.
- Only after code review, passing CI and signed package/certificate/upgrade checks may a **separate** original-certificate production APK be built. Ask for explicit approval before merging to production or publishing a GitHub release.
- Do not transplant unrelated changes from the reference fork automatically or modify other ArtCraft apps.

## Known risks at start of this candidate
- PDFCraft 0.17's updater now uses `craft_update::CheckResultDialog`; Android Help interception must remain functional without triggering the desktop updater.
- egui/eframe 0.37 and major upstream UI changes may require a deliberate new Android launcher adaptation. Automated tests must reveal this; successful unit tests alone are not sufficient.
- A passing disposable-key build is **not** a data-preserving install-over update.
