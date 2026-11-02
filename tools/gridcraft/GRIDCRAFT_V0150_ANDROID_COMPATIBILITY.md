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

## Requested Android feature matrix

| User-requested feature | Decision for GridCraft v0.15.0 |
| --- | --- |
| Automatic saving and recovering workbooks | Pending: audit safe local snapshots, interrupted writes, SAF write acknowledgements and recovery prompts before enabling. |
| Auto-build on commit | Preserve source-audit PR CI; no signing/publishing on commit. Add a non-production ARM64 candidate after port compatibility is resolved. |
| Auto-save/restore session | Pending: validate restored sheet tabs/selection and SAF access grants after process death. |
| Two-finger scrolling | Preserve Android runtime gestures; verify grid and ribbon handling on physical tablet. |
| Better mobile UI scaling | Preserve display-density handling; retest ribbon/menu layout in portrait and landscape. |
| GPU acceleration | Keep working renderer fallback; hardware path must pass Android GPU/driver tests. |
| Long press to right-click | Preserve touch-to-pointer translation; verify no collision with cell editing. |
| Adaptive icons | Preserve verified glossy green Gc assets and launcher adaptive mask/padding. |
| Adaptive cursor | Keep compatible pointer inputs; validate hardware pointer and edit focus behavior. |
| Duplicate file naming | Implement/test `sample (1).xlsx` rather than `sample.xlsx (1)` after identifying the actual Android SAF save path. Pending. |

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
