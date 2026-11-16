# VectorCraft v0.24.1-android.14 — heavy Illustrator AI pan / texture reuse TEST ONLY

## Source and goal
Test on HONOR MagicPad 4 (Adreno 829, Vulkan). The current Android.13 screenshot of an imported Vista Kepong brochure at 95.06% zoom shows **60 FPS, 62.5 ms render and 3.7 ms UI** (previous Android.12 sample at 40.43% zoom was 4 FPS, 302.8 ms render, 233.2 ms UI). Those differ in zoom and document area, so no causal percentage improvement is proven. A separate Android.14 candidate builds on the successful Android.13 test branch.

## Reviewed optimization
Pinned upstream v0.24.1 already has display image mipmaps, cache, a background render worker, 64-MiB retained-frame budget, partial rerendering and reduced-resolution uncovered fill. Do not duplicate those. Do not increase the Adreno driver's **8192 px maximum 2D texture** or bypass the hardware limit.

In cached whole-pixel panning, Android.13 allocated and zero-filled a full RGBA frame and copied preserved rows from the old frame. Android.14 attempts the same pixel shift *in place* by moving owned worker-buffer bytes with overlap-safe `copy_within`, then clears only newly exposed strips. It retains a byte-for-byte original shift implementation for all non-Android platforms, and Rust tests compare outputs for many frame sizes, directions, 0 movements, and beyond-edge movements.

The worker still renders newly exposed document strips exactly as before and falls back to full-frame rendering when necessary. It retains original pixel formats, artboards, text, images, graphics diagnostics, scrolling, stylus tools, updater, saving, and export settings. Nothing changes permanent signing/publishing. Potential gain is reduced CPU allocations and memory copies during eligible panning, not guaranteed faster rendering of every still frame.

## Compare both test APKs (same .ai, same zoom/region)
1. Keep the official published VectorCraft in place and install this separate `VectorCraft Performance Test` candidate. Keep a backup of the Illustrator source. Do not trust "opened with 3 notes: linked pictures show the low-res..." to mean full linked originals are present; source links must still be resolved.
2. Open exactly the same brochure/artboard at 40.43%, then 95.06%, on Android.13 and Android.14. Compare FPS and render/UI timings while actively swiping left/right and up/down across the same scene at similar device temperature. Repeat each 3 times.
3. Test with the big group selected and deselected; View → Hide Edges versus Show Edges; two-finger touch pan/pinch and trackpad pan/pinch; stylus hover without contact; stylus button/wheel. Confirm selection boxes and art are unchanged and no exposed edge strips are blank after movement stops.
4. Test typed text in imported .ai and a new document; Ctrl+Z, Ctrl+Shift+Z, ESC, V/T/H, D/S/C, Ctrl+Q relaunch 10x; in-app update notification/download gating; and file save/open. Verify original full-resolution output (when source images exist).
5. If performance is still lagging, use the Android.13 UI/selection diagnostic and profiler to find render-stage work. This build does not claim to fix high render cost for static, unchanged artwork.

**Gate:** only original user-tested device PASS may authorize a later production branch and permanent signed release. This workflow must produce a disposable-signed ARM64 APK as an Actions artifact.