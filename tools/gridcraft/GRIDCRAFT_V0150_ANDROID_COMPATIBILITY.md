# GridCraft v0.15.0 Android upstream compatibility review — 2026-11-02

**Status: source-only audit. No v0.15.0 Android APK has been compiled, signed, installed or released.**

## Verified inputs

- Official Storytold GridCraft stable: `v0.15.0`, released 2026-11-01 19:18 UTC, tag commit `30b210b4ef03b30616923465efa70766cefba379`; workspace version `0.15.0`. Do not follow unpinned `main`.
- Latest user-tested Android release: `gridcraft-v0.11.1-android.4-ctrlw-dcs-fix`, source `720fab9eaa178da485750009f1a2782026da6286`. Do not replace the tested signing identity or install-over package.
- Porting reference: `MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`. It is not a substitute for the latest tested GridCraft-specific overlays.
- The 4 GiB shared-font scan-byte budget from pending PR #101 has now been ported into this review branch atop the tested Ctrl+W and D/C/S baseline. It uses long arithmetic, preserves the previous cache when exhausted and has a separate Java boundary regression. Existing 200-file / 200-directory and 32 MiB per-file caps remain; a 4 GiB budget does not imply scanning 5,000 files. Android compilation and SAF device scanning remain unverified.

## Immediate compatibility findings

The v0.15.0 release updates the spreadsheet UI and shared update handling, and changes exact source anchors used by the existing Android v0.11.1 patcher. The read-only CI compatibility report identifies which anchors changed. Mismatched patches MUST fail closed; do not force text substitutions or claim v0.15.0 is already an Android port. Reconcile newer upstream update dialogs with the Android-only checker that verifies uploaded GridCraft APK assets.

**No production build workflows or secrets are changed by this review.**

## Verified requested Android feature matrix (2026-11-02)

**Evidence separation:** The latest public GridCraft APK is based on the tested v0.11.1 Android port; this PR is an upstream **source-review** branch, not a compiled v0.15.0 port. The reviewed reference builder is deliberately pinned to `MostafaXS1/artcraft-android@ac54d62` (2026-10-20), whereas that independent reference project's `main` is newer (2026-10-27 as checked 2026-11-02). Features described in the reference project's newest README/CHANGELOG are **not** automatically present in this repository's old pinned builder or any GridCraft release.

| Owner-requested feature | Observed in working port/review | Safe v0.15.0 integration requirement and acceptance evidence |
| --- | --- | --- |
| **Auto-save and recover documents** | Android SAF save/close acknowledgement exists in tested v0.11.1 overlay; **unattended auto-save and recovery not verified**. Newer reference builder documents periodic SaveMirror/SAF auto-sync, absent from the pinned builder. | Start with bounded atomic **local recovery snapshots** only; test crash/kill and restore prompting, never silently overwrite SAF original. Reconcile dirty revisions, Ctrl+W and repeated D/C/S. Opt in to SAF background writes only after independent interruption and consent tests. |
| **Auto-build on commit** | ✅ This draft PR already triggers GitHub Actions **source checks** on changes. **No v0.15.0 APK auto-build exists**. | After the five changed APIs compile, add branch-scoped, non-production ARM64 candidate CI with a disposable key and unique test package; no signing secret, auto-merge, tag or release. Require actual output APK + ABI/package/artwork/feature verification. |
| **Auto-save and restore sessions** | ❓ No verified GridCraft-on-Android process-death session restore. May have desktop session primitives. | Persist open sheet/workbook selection and supported window state without storing credentials/invalid SAF grants. Prompt and restore only accessible documents after a cold launch, and preserve fresh documents and dirty buffers; device test. |
| **Two-finger scrolling** | Newer reference project's winit/egui code describes touchpad and touch-screen scroll/pinch; not proven in pinned GridCraft APK. | Merge only validated gesture input, test spreadsheet scroll vs pinch vs cell selection/drag; do not introduce keyboard-focus or IME regressions. HONOR MagicPad 4 device test in portrait/landscape. |
| **Better UI scaling** | Newer reference source implements optional 150% initial scale for **phones** (<600 dp), preserving tablets' user-set scale. Not verified in this pinned GridCraft version. | Respect saved GridCraft scale and tablet display density; introduce only first-launch phone bootstrap if compatible. Validate formula bar, ribbon and on-screen keyboard accessibility. |
| **GPU acceleration** | Existing pinned builder requests eframe wgpu Vulkan/GL backends, but real hardware adapter, render/fallback and GPU identification require evidence. | Preserve working renderer and CPU fallback. Verify device-selected adapter, large workbooks, SAF picker lifecycle, Vulkan/GLES fallback and native `.so` ABI. Do not claim GPU acceleration from the existence of wgpu options alone. |
| **Long-press to right-click** | Android reference handles pointer secondary clicks; exact GridCraft finger-hold → secondary-click behavior unverified. | Only emit a secondary click after deliberate long press, avoiding accidental cell edit/selection and text input. Test touch, stylus, mouse, trackpad and cancel gestures. |
| **Adaptive icons** | ✅ Approved Gc icon source and padding/adaptive resource staging exist in the tested Android overlay, with exact SHA checksum checks. | Retain approved glossy green Gc artwork and do not change identity; inspect actual packaged foreground/background/monochrome and legacy icons with APK tooling, plus visual launcher test. |
| **Adaptive cursor** | Newer reference project documents a shared pointer-icon bridge restored in v35; older pinned builder may not have the same working hover handling. Not verified for GridCraft. | Port only if compatible with GameActivity/winit input. Test I-beam, selection, resize and drag cursor over real mouse/trackpad on HONOR; retain default pointer as fallback and don't disrupt physical keyboard focus. |

**Do not mark a feature complete merely because the new reference repository claims it or its source has a hook.** Mark Android functions as integrated only after the targeted code lands on this branch, ARM64 build passes, and the relevant device/user tests pass. Preserve the existing working Ctrl+W, D/C/S, Esc, SAF font imports and public signer continuity throughout.

## Existing Android functions that must not regress

- `com.artcraft.gridcraft` package and original permanent signing certificate compatibility.
- Ctrl+W while typing in a cell, repeated D/C/S modal dialogs, hardware Esc exit editing, and safe save/close confirmation.
- Approved glossy green Gc launcher, SAF file picker, XLSX open/save/reopen and export.
- Import TTF/OTF, shared font folder recursive scan, refresh/status, approved font catalog, 4 GiB scan review.
- Manual verified GitHub Android APK release checks, optional startup checks, visible feedback, no silent self-install.

## Next gates

1. Port new upstream `v0.15.0` APIs into the isolated GridCraft-only Android overlay, preserving exact baseline keyboard, save, and font behavior.
2. Confirm the ported 4 GiB scan from PR #101 in a real ARM64 build and device SAF refresh; do not claim that existing per-file, per-folder or file-count limits changed.
3. Produce an isolated disposable-key ARM64 candidate; verify compiled native libraries, package ID, launcher icon and feature tests. Do NOT replace an installed original-key production build with temporary-key test APK.
4. Tablet regression tests: repeat Ctrl+W then D/C/S, Esc during cell editing, XLSX round-trip, imports, nested fonts, 2-finger gestures, scaling, GPU fallback, long-press, cursor, autosave/recovery if implemented, and duplicate extension handling.
5. Independently verify production versionCode is greater than the released `16780036` and signer matches the user's existing certificate; request owner approval before any production merge/signing/release.

**Release gates in this review remain closed:** `upstream_review_only=true`, `version_code_reserved=null`, `build_approved=false`, `publish_approved=false`.
