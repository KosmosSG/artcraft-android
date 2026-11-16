# VectorCraft v0.24.1-android.13 — complex .ai performance (ARM64 TEST ONLY)

## Evidence and target
On the owner's HONOR MagicPad 4, a brochure imported from Illustrator at 40.43% zoom with a large group selected was observed at **4 fps**, with **render 302.8 ms** and **UI 233.2 ms**. These on-screen numbers are not a reproducible benchmark; obtain the same file on the same device and compare stable measurements.

## Narrow, reversible change
- Start from the already published **v0.24.1-android.12** code, not an unreviewed upstream bump.
- The pinned VectorCraft v0.24.1 implementation already has cached canvas rasters, a background rendering worker, reprojected frames, and complexity-safe selection bounds.
- Reduce the **Android-only selection and hover UI overlay budget** from 100,000 to 8,000 points so extreme groups use their selection bounds instead of a huge UI mesh. The desktop threshold remains 100,000. Document content, geometry, image resampling, save/exports, original renderer, and hit testing are unaffected.
- Add low-overhead Android-only VC_PERF_SELECTION_OVERLAY and VC_PERF_DOCKED_PANELS elapsed-time logs for frames exceeding 24 ms and 30 ms. The latter includes canvas UI. Renderer timing is already present in the app status bar. Never log names, paths, text or document contents.
- No broad GPU rewrite, forced 165 FPS, new raster cache, or lossy export.

## Test sequence on same large imported .ai
1. Back up the source Illustrator file first. Install the **separate** disposable-signed VectorCraft Performance Test app, preserving the published app.
2. Open the brochure and wait for image decoding and its first complete frame; note FPS and render/UI ms at the same zoom, ideally three repeated 10-second pan/zoom sessions. Compare the published Android.12 app and new Android.13 test under similar thermals and refresh settings.
3. Test with nothing selected; a large group selected; View → Hide Edges then Show Edges; trackpad and two-finger touch panning and pinch; hover selection. If performance only improves on selected groups, keep the scoped UI optimization and investigate other slow paths separately.
4. Ensure no missing artwork, displaced text, group/bounding-box errors, broken links or low-resolution saved/exported images. Test undo Ctrl+Z / redo Ctrl+Shift+Z, typing in new and imported .ai documents, ESC, V/T/H, D/S/C, Ctrl+Q/relaunch 10×.
5. Verify stylus hover pointer **without a prior touch**, button-wheel, 8 segments and customization, adaptive cursor, in-app updater and PhotoCraft-style bottom notifications.
6. Inspect ADB VC_PERF_SELECTION_OVERLAY / VC_PERF_DOCKED_PANELS and existing renderer stats if the same file still lags. Do not treat a successful build as a performance pass.

**Release gate:** no merge, original signing, production package overwrite, tag, or published release until user confirms device PASS. APK must be a separately installed temporary-key ARM64 test artifact.
