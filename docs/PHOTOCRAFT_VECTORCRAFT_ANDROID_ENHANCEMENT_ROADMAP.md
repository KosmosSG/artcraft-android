# PhotoCraft + VectorCraft Android — implementation roadmap
Review-only development ledger | 23 October 2026 | `KosmosSG/artcraft-android`

## Safety requirements

- **Do not enable automatic upstream synchronization, unattended merging, automatic production builds, release signing or GitHub publication.** GitHub push-based CI on reviewed branches is permitted for validation only.
- GitHub Releases only, no Google Play. Preserve the permanent **separate** production signing identities, `com.artcraft.photocraft` and `com.artcraft.vectorcraft`, original app data, saved documents, custom TTF/OTF/shared SAF fonts, physical keyboard, touch docks, GPU diagnostics, updater and approved glossy Pc/Vc branding.
- All source compatibility tests use official immutable upstream tag and commit SHA. Do not treat the suite `main` branch as the source of a previously published app; branches must derive from released app source.
- Before publication, require ARM64 Java/Rust test and build checks, inspected APK package/ABI/versionName/versionCode, original certificate fingerprint and checksum, complete HONOR MagicPad 4 install-over-existing test and explicit approval. Never uninstall the existing app as a testing prerequisite.

## Baseline releases and implementation branches

| App | Published baseline | Reviewed upstream | Active review PRs | Evidence |
|---|---|---|---|---|
| PhotoCraft | `photocraft-v0.12.0-android.1`, published code `16790002` | `storytold/photocraft@ff4738810134d7f7e68b49f2e4f231b686282ff3` (v0.14.0) | #23 integration, #28 update dock | Keep approved Pc icon, 6 menu commands and original cert |
| VectorCraft | `vectorcraft-v0.14.0-android.5`, published code `16780805` | `storytold/vectorcraft@10190753ef356ce8de7592626bcb99fd69db467c` (v0.16.0) | #22 dock/update maintenance, #26 upstream compatibility | Keep Vc icon, SAF/IME/fonts/shortcuts, original cert |

## P0/P1 — integration stability: do these first

### PhotoCraft #23 — official v0.14 Android source
1. Preserve the released v0.12 adapter and all six Android menu IDs; use the verified v0.14 menu port instead of trying to apply the old v0.12 patch twice. Maintain exact upstream pin, approved Pc icon and original file/IME/GPU/keyboard code.
2. Run the guarded compatibility workflow and make a **separate-package**, temporary-signed `com.artcraft.photocraft.candidate` APK. The candidate is not a production update and cannot replace the installed app. A *future production* app's versionCode must exceed `16790002`.
3. Validate the Test APK on HONOR MagicPad 4: open/save/import, PSD/native export, fonts across restart, shared folder, left/right modifiers, touch shortcut pad, rendering diagnostics, and updater.
4. Keep draft/no release until all gates pass.

### PhotoCraft #28 — update display maintenance
- Dock status before drawing the canvas; no floating update window.
- Manual check immediately shows progress and feedback; handle no release, up to date, update available, offline and timeout; allow dismiss.
- Keep startup checking opt-in and off by default; validate only app-specific GitHub release tags and signed assets.
- Regression tests cover dock-before-editor, painting area, orientation and callbacks.

### VectorCraft #22 — existing Android UI
- Bottom dock GPU diagnostics, never floating; reserve actual document area. Visible non-blocking update status, 30-second watchdog and dismiss.
- Existing push CI source/Java/ARM64 checks pass; candidate APK, permanent signing and on-device regression tests are **not** proven by this alone.

### VectorCraft #26 — official v0.16 source
1. Immutable source `v0.16.0@10190753ef356ce8de7592626bcb99fd69db467c`. Reuse released v0.14 Android adapter plus #22 fixes, original Vc artwork and pinned builder in disposable CI checkouts.
2. First perform read-only Python/Java/Rust ARM64 checks, then fix upstream API changes without dropping Android features. Maintain `com.artcraft.vectorcraft`.
3. Only after successful compile authorize a separate-package `com.artcraft.vectorcraft.candidate` temporary-key test build; keep private permanent keys unavailable to public candidate CI.
4. Verify installed Vc settings, data, fonts and drawings survive a future *original-signed* update and that production `versionCode > 16780805` (and every newer actual installed/published code).

## P2 — unified keyboard shortcuts and tablet workspace
**Independent app PRs after compatibility gates.** Reuse official shortcut registry, PhotoCraft's modifier tracker and touch pad, and VectorCraft's modifiers/keyboard shortcut dialog/touch dock. Add user profiles (Photoshop-style/Illustrator-style), shortcut edit/search, conflict detection, secure saved JSON and optional explicit SAF import/export. Respect native IME, Chinese text, left/right Ctrl/Shift/Alt, focus loss, Android Back, editor text fields and no synthetic untrusted events. Add optional saved landscape/portrait workspaces, adjustable non-floating docks and show/hide commands. Tests must cover modifier sequences, shortcuts, text editing, rotation, settings restart and both tablet and hardware keyboard.

## P3 — autosave, recovery and professional exports
Audit upstream recovery and export first. Extend Android app-private atomic recovery/retention safely; do not overwrite originals on SAF permission failures, cloud-provider errors or process kills. Verify round-trip compatibility with native project files; PhotoCraft PSD/PSB/PNG/JPEG/WebP/TIFF as supported; VectorCraft SVG/PDF/PNG/JPEG/WebP and multi-artboard export as supported. Show explicit export options, cancel/progress/error, deterministic file naming and safe overwrite prompts. Tests cover large files, document content preservation, backgrounds/foregrounds, interrupted writes and Android SAF round trips.

## P4 — PhotoCraft selection and non-destructive background removal
Reuse upstream Quick/Object/Subject Selection, Select and Mask and existing layer-mask operations. Add Android-friendly background removal that produces an editable mask, never destructively erases the sole source layer; preserve preview, edge refinement, undo/history and project/PSD re-open. Prefer fully offline processing, bounded resources, and review licensing/size before including any model. Test difficult edges, transparency, cancellation, low-memory failure and colour-depth preservation.

## P5 — VectorCraft Image Trace and print preflight
Reuse upstream `vectorcraft-trace`, Shape Builder, snapping, CMYK document and PDF export rather than duplicating algorithms. Surface touch-friendly threshold/colour count/smoothing/preview and editable traced paths, with bounded segments and undo. Printing work must validate bleed/trim/safety, colour profiles, embedded fonts, crop marks and PDF/X claims against the actual upstream implementation; do not mark an export print-ready merely because it bears a PDF extension. Validate traces, vector round trip, multi-artboard export, PDF text positions and CMYK values on fixtures.

## P6 — shared creative assets and user-triggered automation
After the shared TTF/OTF SAF folder works on the exact signed test APK, extend voluntarily to swatches (ACO/ASE where supported), palettes, gradients, brushes, patterns and templates. Each app must request its own persisted read-only SAF permissions, cache bounded validated data separately, detect duplicates/conflicts, survive revoked permissions and respect third-party asset licensing. Add only explicitly **user-triggered** batch actions reusing upstream command/automation engines, with dry run, preview, overwrite consent, cancellation and local-only processing. Never conflate creative batch actions with prohibited automatic upstream GitHub syncing, signing or release publishing.

## Deliverable and test contract for every enhancement
1. An isolated app-scoped branch/PR with immutable upstream source identity and audited file changes.
2. New/changed unit tests for feature preservation and failure handling; no loss of legacy Android functionality.
3. Rust Android ARM64, Java SAF/IME and manifest checks; a private, temporary-signed Test package before any production APK.
4. Honest test evidence: a CI green check is **not** HONOR MagicPad 4 runtime or permanent signing proof.
5. For production, original per-app certificate + backup provenance, strictly increasing `versionCode`, exact signed APK SHA256, in-place device update, approved changelog and **manual owner authorization** for GitHub Releases only.

### Repository management note
GitHub Issues are currently disabled in this repository; this review-only document provides the development backlog without modifying repository administration.
