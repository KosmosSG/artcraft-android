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

## Owner-verified v0.17.0-android.1 baseline and requested v0.17.0-android.2 fixes (2026-11-02)
- The owner installed the **original-key-signed** v0.17.0-android.1 APK and reported: "Tested. All working." Preserve the previously approved PDF editing, touch, keyboard, SAF, update checker and launcher behavior.
- The owner supplied `PDFCraft.png` (2048 × 2048), with flat bright red `#fb0e00`, the white PDF symbol and `PDFc` lettering. The updated candidate contains a close geometric SVG trace under `assets/pdfcraft/owner-PDFCraft.svg`; the 512-pixel preview differs by about 0.65 mean RGBA channel levels from the uploaded source, as measured before committing. Legacy launcher uses the full red icon, while the adaptive icon uses white-only artwork centered over a separately colored matching red background; verify this on the **physical device**, including circle and squircle masks.
- Integrate the **4 GiB** budget proposal from draft PR #102 into this v0.17 branch, adding the owner's **5,000-font** per-refresh target. Both limits are applied to one SAF tree refresh; Java `long` arithmetic prevents 2 GiB overflow. The directory traversal visits nested folders up to 10,000 folders, counts all discovered TTF/OTF candidates (including rejected fonts), and keeps the existing 16 MiB per-file cap. This is **not** permission to access unrestricted storage or allocate 4 GiB in RAM.
- `tools/font_scan_budget_regression.py` compiles/executes Java checks of the boundary arithmetic and guards against reintroducing 200-file limits. The Android runtime must still be checked with nested folders, mixed providers, duplicates, permission reauthorization, large directories, and storage-space exhaustion.
- `v0.17.0-android.2` needs Android versionCode **16781569** for an in-place update over the owner's verified `v0.17.0-android.1` (16781568). Because cargo-apk2 derives the numeric code from upstream SemVer 0.17.0, the isolated candidate uses a fail-closed manifest edit with binary checksum/payload preservation, zipalign, and **temporary** signing. Check packaged `aapt2 dump badging` and signer before any original-key signing.
- Before publishing, the rebuilt .2 APK needs an **original-PDFCraft-key signature check against the previously published v0.12.1-android.3 APK**, then owner device acceptance specifically for the red icon, nested SAF font scanning (5,000 files / 4 GiB budget), save/edit regression and install-over upgrade. No automatic merge or publication.



## Nine-feature compatibility audit against MostafaXS1/artcraft-android (2026-11-02)

This audit is based on the reference fork's README/CHANGELOG v37 and the PDFCraft v0.17 Android builder's **actual code**. The fork is a guide, **not** an authorized wholesale transplant. Keep the owner-tested .android.2 build intact, and do not destabilize the pending .android.3 visible-font-controls candidate while reviewing these followups.

| Requested Android feature | PDFCraft v0.17 branch implementation evidence | Remaining gate |
|---|---|---|
| Auto-saving and recovering documents | **Partial/implemented recovery snapshots**: official v0.17 `PdfCraftApp::autosave_tick` writes via `RecoveryStore`, with `AUTOSAVE_SECS=60`; builder's `PERSIST_RECIPES["pdfcraft"]` calls `enable_recovery` and installs Android-private config/data directories. | Verify crash-kill/relaunch actually offers the snapshots with real/SAF PDFs. **Separate feature:** ref fork v37 `SaveMirror` auto-sync writes to original SAF URI; current PDFCraft builder only stages/copies on supported picker/save operations, not a verified periodic source URI mirror. Never claim automatic original-document sync yet. |
| Auto-building on commit | **Implemented** on scoped `.github/workflows/pdfcraft-candidate.yml` branch push; no release. | Verify newest source commit had checks; no auto-publish. |
| Auto-saving and restoring sessions | **Implemented for state/prefs**: builder stores `inner.persist()` in `ui.json` and restores it via `inner.restore(json)`; ticks about every 2 s and saves on focus loss/exit. Official `LastSession` uses an opt-in `reopen_last_session` preference (default false). | On device, enable reopen preference, reopen tabs and verify no unwanted overwrite of originals, particularly SAF URI-backed documents and staged files. |
| Two-finger scrolling | **Partial**: existing vendored Android winit supports mouse/trackpad `MouseWheel` and touches; current backend lacks reference fork's distinct two-touch gesture state machine and Android momentum synthesis. Fork v37 documents 12px pan / 36px pinch disambiguation and WordCraft-only app-side guard, explicitly not a vetted PDFCraft port. | Implement and test a **PDFCraft-specific** touch-to-scroll/pinch mapping with no accidental text selection, keyboard popups or regressions. Check physical touchscreen and external touchpad separately. |
| Better UI scaling on mobile | **Partially implemented**: egui native density scaling + upstream v0.17 `ui_scale::sync` / Preferences interface-size factors; fullscreen handling and layout adaptation. Fork adds phone-only 150% first-run bootstrap. | First-launch phone-scale bootstrap can be added to Android shell if guarded by `smallestScreenWidthDp<600` and no existing setting. Leave HONOR tablet scale and user overrides unchanged. Test portrait, split-window and dialogs. |
| GPU acceleration | **Renderer path integrated**: launcher requests `eframe` wgpu feature; upstream renders PDF on supported platform wgpu backend. This does not prove the adapter actually chose a physical Adreno/Vulkan GPU rather than fallback. | Log actual backend/adapter and distinguish Vulkan/GLES/CPU; verify hardware on MagicPad without forcing unsupported GPU features. |
| Holding finger to right-click | **Not verified/absent as explicit gesture**: vendor winit forwards mouse `Secondary` button to Right; finger events remain touchscreen `Touch`. There is no dedicated long-press timer/cancellation to synthesize right-click. | Add guarded long-press behavior in PDFCraft Android touch adapter with timing/move slop, context-menu coordinates, cancellation on scroll/second pointer and proper release event; test egui widgets and text selection. |
| Adaptive icons | **Implemented**: APK build includes legacy raster icons and a PDFc white foreground + matching red adaptive background (with owner icon). | Device verify masking and resource identity. Material You monochrome support remains optional/unverified. |
| Adaptive cursor | **Not verified/absent bridge**: egui defines desktop contextual `CursorIcon` values and winit handles hover/mouse events; current PDFCraft Android backend's `set_cursor` is effectively a no-op (no reference fork's `egui-winit/pointer_icon.rs` JNI bridge). | Port only a tested Android PointerIcon JNI bridge, preserving compatibility with existing API level and rendering, then test physical mouse and trackpad I-beam/resize/hand changes. |

**Important:** A CI green tick proves compilation, ABI, package integrity and covered tests; it cannot certify recover-after-kill, two-finger gestures, long press, real GPU driver choice, pointer shape, or UI usability on hardware. Keep these pending until the owner tests an original-PDFCraft-certificate-signed candidate. **No publication** until separately approved.


## Owner Android.3 UI feedback → Android.4 toggle (2026-11-02)
- Owner tested **original-certificate-signed** `v0.17.0-android.3` on HONOR MagicPad 4. All 3 font actions were visible but the extra top strip (above native PdfCraft File/Edit/View/Sign/Window/Help menu) consumed screen space. Owner requested an option to show/hide top panel **or** put actions into the menu UI.
- Chosen nonintrusive solution: **native View ▸ Android tools panel** check item. Toggling off removes the whole toolbar from egui layout, not just the buttons. When on, a dedicated **Hide panel** button offers one-click dismissal. The same File/Help update and SAF/font callbacks remain unchanged.
- `tools/pdfcraft/android_tools_menu_patch.py` makes guarded Android-only edits to upstream `crates/ui-egui/src/menus.rs`; the exact pinned official v0.17.0 source must have unambiguous anchors. Desktop menu is unaffected; no silent fallback.
- `templates/android/pdfcraft_mobile_java.txt` persists the shown/hidden preference in `SharedPreferences` under `pdfcraft.tools.visible`, defaulting **true** for existing users. `Mobile::new` reads it once and the native View toggle synchronizes only on changes; subsequent launches respect the user choice.
- Candidate `v0.17.0-android.4`, `versionCode 16781571` (strictly higher than .3 `16781570`). **No other nine-feature audit backlog changes are included in Android.4.** It is only a toolbar visibility usability fix.
- Before owner installs: verify exact branch candidate CI, signed APK same original PDFCraft certificate as `.android.3` and published baseline, unchanged APK payload from build to signed, correct ARM64 and version. On device: turn off from View menu and confirm no upper strip, turn on via View again, hide via toolbar button, force-stop/restart and confirm preference persists, verify font pickers/refresh, PDF editing and saved documents. No public release until separate approval.

## Owner light-theme toolbar contrast regression → Android.5 (2026-11-02)

The owner confirmed that the `.android.4` toolbar controls, View menu toggle, and dark theme look good on their HONOR MagicPad 4, but attached screenshots show **black text on an unpainted black native Android strip when PDFCraft is switched to its light theme**. The Android tools panel used `parent.group()` without a frame fill: PDFCraft's egui theme set dark text for light mode, but the window underlay remained Android black.

The isolated fix in `templates/android/pdfcraft_mobile.rs` replaces the transparent group with `egui::Frame::group(parent.style()).fill(parent.visuals().panel_fill)` on every frame, and expands the painted frame to the available window width. This intentionally follows **the currently active PDFCraft visuals**, not a hard-coded white color, so white/light and black/dark themes remain readable and a theme switch updates the panel without restart. All font selection, refresh, status text, Check updates, Hide panel, View toggle and persisted visibility behavior remain unchanged.

Target **v0.17.0-android.5** (`versionCode=16781572`), compiled with the disposable builder test key only. No original PDFCraft keystore or second signing job for candidates: the owner accepts backing up app data, uninstalling the prior test APK, and installing this fresh candidate. Before final release separately verify light/dark toolbar contrast, full-width fill, hide/show and persistence, fonts/4 GiB/5,000 scan, PDF read/edit/save, adaptive PDFc icon and ARM64 package. **Do not** claim the other requested Android gestures/cursor features are included or publish without approval.
