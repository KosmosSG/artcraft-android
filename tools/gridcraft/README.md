# GridCraft Android — isolated source audit (draft only)

This is **GridCraft**, the spreadsheet app previously called "ExcelCraft" in conversation. Do not rename the upstream project or touch any other app's branch, workflow, key, artifacts or releases.

## Verified input and Android target
- Upstream: https://github.com/storytold/gridcraft
- Official **stable** release: https://github.com/storytold/gridcraft/releases/tag/v0.9.0 (published 2026-10-20).
- Release tag `v0.9.0` resolves to immutable commit `a2cc4b42cac6e2c41bae71fba4607300755a0b47`.
- MIT OR Apache-2.0 for core source; audit per-asset and dependency licensing, including upstream ATTRIBUTION.md, NOTICE, docs/brand/LICENSE-brand.txt and external fonts, before redistribution. Do not incorporate Microsoft assets.
- Implementation reference: https://github.com/MostafaXS1/artcraft-android/tree/ac54d62d9d2d6f663295a4afd8972a7a3e79f9af, *not* a replacement for the current fork's working enhancements.
- HONOR MagicPad 4 / MagicOS 10; `arm64-v8a`.
- Intended production identity: `com.artcraft.gridcraft`. Version name `0.9.0-android.1`; planned artifact `gridcraft-0.9.0-android.1.apk`.
- **Do not assign a production versionCode or sign a release** until existing installed, signed and published GridCraft identities have been checked. This audit found no GridCraft release in this fork and no dedicated GridCraft signing repository in the connected account; external/local signing state remains unknown.

## Existing code: do not confuse presence with device validation

The fork's generic builder already declares GridCraft in `lib/build-common.sh`. Its GRIDCRAFT SAF recipe and `lib/file_associations.py` advertise document open and save, incoming VIEW/SEND intents, XLSX/XLSM/XLS/XLSB/ODS/CSV/TSV associations, IME, and font fallback. Read the exact file association registry to distinguish advertised types from successfully supported round-trips. The official GridCraft UI exposes `SheetApp::new(Session::new(), Services)`, `Inbox`, `run`, `file.exportPdf`, save/open, clipboard services and print services. The upstream desktop print backend is not evidence of Android printer support. No GridCraft APK or end-to-end device test was performed in this PR.

## Requested features and next integration gates

| Area | Grounding / required validation |
| --- | --- |
| Document picker | Inspect the generated GridCraft SAF recipe, Java Activity, open/save/save-as/export callbacks and inbound VIEW/SEND; test file-provider URIs, cancelled picks, collision handling, permissions, large workbooks and actual saved bytes |
| Spreadsheet correctness | Verify workbook formulas/recalc, formats, merged cells, styles, sheets, charts, import fidelity and XLSX save/reopen via representative self-generated test files; do not claim full Excel fidelity, macros or lossless round-trip |
| Input & tablet ergonomics | Audit generated IME bridge, text composition, hardware Ctrl/Alt modifiers, GridCraft's existing keymap commands and hit targets before adding customization or optional docked Shortcut Pad; no floating font UI |
| Fonts | Use Android system fallback already in builder; separate, opt-in SAF-importable TTF/OTF folder support only after verifying GridCraft's own font catalog and license restrictions |
| Print/PDF | Confirm `file.exportPdf` works with SAF and Android printing only with explicit platform print service; no desktop print commands on Android |
| GPU & updates | Report actual active backend/renderer and fallback, never assume Vulkan works; add consented startup/manual checks and preference after validating release metadata and signature identity |
| Security | Do not expose or use production keys for draft CI. Candidate only with disposable key, isolated app identity and provenance/hashes; no automatic merge/publish |

## Uploaded icon — exact-asset gate

The user-provided PNG named `Glossy Green Xc App Icon(1).png` is **1254×1254** with SHA-256
`8c0db50831bd715812212c04f156029cfeabd1be82cf5bd777c9db5547063d19`.
It visibly spells **Xc**, and the user requested using it as supplied, rather than changing the lettering to Gc.
Target source path is `assets/gridcraft/launcher-source.png`.
The uploaded binary **has not yet been committed** to this repository. Do not use a mock icon or claim it is installed. The image may be integrated only after exact SHA-256 verification and launcher density/adaptive foreground/background tests.

## Release safety and remaining blockers

1. Confirm any prior GridCraft installed package/versionCode, certificate digest and recoverable dedicated permanent signing key; if none exists, create a **GridCraft-specific** signing identity with encrypted recovery copy, after explicit evidence review. Never reuse PhotoCraft/VectorCraft/etc keys.
2. Add the exact uploaded icon to this branch and verify its checksum. Preserve its solid dark background, artwork and Android round/adaptive safe zone when packaging.
3. Use only the pinned official source commit and audit Rust Android target dependencies, Java bridge and `cargo-apk2`. Prepare a **manual**, bounded GitHub Actions ARM64 candidate with a **disposable** key and isolated `.candidate` package, no release signing. Gate exact versionName, reserved monotonically increasing versionCode, ABI, launcher resources, hash, candidate cert and manifest consistency.
4. Only after a compile/tested candidate, verify real spreadsheet workflows on-device. Device behavior **untested** until the user checks.
5. Separate production signing (dedicated existing certificate only) from compilation. Require unchanged pre-sign/post-sign payload except signing metadata, certificate continuity, GitHub release checksums and updater metadata before publication.
6. Later, add read-only upstream polling and review PRs first. Promote only compatibility-checked changes; do not activate schedules on main, replace source history, move tags, force-push, or erase app enhancements merely to pass CI.

This PR's GitHub Actions check is **read-only source provenance only**: no APK compilation, key creation, release publication or scheduling.

## PhotoCraft-parity Android source staged on this GridCraft-only draft branch

The following code is now present, **not yet compiled into an APK or device-tested**:
- `android_addons/GridCraftJavaMethods.java.inc`: Android SAF TTF/OTF single-font picker; validated size (32 MiB limit) and sfnt signatures; persisted app-private font location; Android document-tree permission and bounded nested-folder refresh (up to 200 directories / 200 imported fonts) to a private shared cache; release-feed parsing for public `gridcraft-vX.Y.Z-android.N` tags only; manual checks, saved opt-in startup preference, errors/no-public-release feedback and allowlisted browser links.
- `android_addons/gridcraft_tools.rs`: a collapsible, **non-floating** GridCraft Android controls section, with import/select/refresh buttons, update preference and safe release link. An optional in-session touch Shortcut Pad runs GridCraft commands `edit.undo`, `edit.redo`, `sheet.previous`, `sheet.next` and `view.zoom`.
- `android_addons/overlay.py` and `install_overlay.py`: staging-only code insertion into the **GridCraft** generated Rust/Java launcher in a disposable copy of the pinned Android builder. Other app sources and workflows must not be modified. The overlay adds Android `INTERNET` permission for opt-in read-only GitHub checks.
- `test_overlay.py`: offline checks to protect app isolation, expected insertion points, appropriate SAF Java methods and no production signing/release actions.

### Behavior and limits

GridCraft v0.9.0's font catalogue uses a process-lifetime `OnceLock`; both direct import and shared-folder refresh require **restarting GridCraft** before the imported families appear in its font menus. The shared Android Files folder is selected *per app* (Android SAF permissions are per application) even when several ArtCraft apps point at the same underlying folder.

The update checker is **Android APK release** specific. It does not mean a newly published upstream GridCraft desktop release is already available as a compatible Android APK. GitHub API failures and no published Android releases are separate statuses. **No auto-download/installation**.

The Shortcut Pad is an in-app proof of concept with GridCraft-native commands; it does not currently persist its show/hide state, expose customizable hardware-key mapping, create a fully docked independent widget, or replace GridCraft's existing shortcuts. GPU information is intentionally labelled unverified; no Adreno/Vulkan claim is made without a runtime adapter report.

### Before a candidate or release can be claimed

1. Verify the overlay against the pinned upstream/ref-builder source by compiling a disposable-key, isolated-package ARM64 candidate. The current CI runs only Python audits, not Java/Rust/NDK compilation.
2. Verify generated manifest, activity, SAF picker result dispatch, font load after restart, preference persistence, scanner limits, updater response types and separate release URL allowlist.
3. Verify formulas, recalc, formatting, ranges, XLSX/CSV/PDF, clipboard/IME/hardware modifier keys with synthetic workbooks; do not claim Excel macro/round-trip compatibility.
4. Validate UI layout on MagicPad 4, then refine Shortcut Pad placement and customization and GPU backend reporting from actual runtime data.
5. Integrate the exact user-uploaded Xc launcher artwork (matching source SHA in lock); **the binary has not been uploaded into GitHub**, so APK branding remains unverified.
6. Only then verify permanent signing identity, certified versionCode continuity, reversible encrypted key backup and separate signed release workflow. Do not publish or enable main-branch schedules from this draft.
