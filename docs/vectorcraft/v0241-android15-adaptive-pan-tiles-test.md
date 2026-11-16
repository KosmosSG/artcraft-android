# VectorCraft v0.24.1-android.15 — adaptive partial canvas redraw (ARM64 TEST ONLY)

## Performance baseline

Owner reported Android.14 is smoother when opening large Illustrator AI artwork. Latest screenshot showed approximately **60 FPS, render 22.5 ms, UI 4.3 ms** at 107.45% zoom, no selection, on HONOR MagicPad 4 (Adreno 829; 8192-pixel maximum 2D Vulkan texture). Compared with previous Android.13 screenshot at 95.06% and selected group, those values cannot establish a percentage speedup. Measure same pan/zoom and same artboard state on-device.

## Scoped Android.15 change

Pinned upstream VectorCraft 0.24.1 already has image mipmaps, low-resolution filler, an off-thread worker, existing image-store budget, per-document raster caches, partial redraw support and frame-reprojection. Do NOT rewrite those or increase the GPU hardware texture limit. Android.13 selection overlay and Android.14 in-place RGBA pan buffer reuse are preserved.

The Android.15 patch changes **only Android canvas onscreen worker redraw quantization for small whole-pixel pans**. The previous exposed strips were enlarged to full eighths of each screen dimension. Short pan movements now use sixteenths, reducing the area that needs re-rendering while still covering all newly exposed screen pixels. Large pan movements keep the original eighths and non-Android platforms retain all original behavior. Existing full-frame fallback, the settled-frame high-resolution redraw, image colors and PDF/AI/saving/export are unchanged. There is no claim that this accelerates still-frame rendering.

The worker also samples slow (>24 ms) render jobs without any file names, coordinates or artwork. Rust unit tests check that all exposed pixels remain covered at many canvas widths and pan directions and that large movements preserve the original path.

## APK gate

The CI run must produce a **temporary-key, distinct-app-ID** VectorCraft v0.24.1-android.15 ARM64 test APK. No permanent signing, no GitHub Release, no merge to published stable code, and no overwriting Android.14 or other stable installations.

## Device testing: compare Android.14 and Android.15

1. Install this separate Android.15 test APK; preserve Android.14 and production. Open the same *Vista Kepong_Simplified Brochure* Illustrator file from the same source, with artboard 4 visible at identical zoom (try 107.45%) and similar thermal conditions.
2. Make repeatable short pans left/right/up/down with two fingers and with the trackpad. Check FPS and render/UI ms while moving and after the canvas settles. Test long/fast pans too. Repeat each comparison 3 times.
3. Inspect exposed canvas edges: no blank seams, misaligned lines, ghosting, shifted photos or missing art after movement settles. Compare screenshots with the previous candidate.
4. Test pinch zoom to/from different scales, selected complex group and no selection, and View → Hide Edges. Report whether the actual navigation is smoother, equal or worse.
5. Preserve original .ai typing and new-document typing, Ctrl+Z and Ctrl+Shift+Z, ESC, V/T/H, D/S/C, Ctrl+Q relaunch, touch-pan direction, trackpad, immediate no-touch stylus hovering pointer, stylus button wheel/configuration, in-app updater, launcher icon and compact Vc menu.
6. Check saved/exported content. Linked images showing low-resolution proxies may require relinking the original photographs; optimized textures cannot recreate missing linked source data.
7. If performance worsens or image seams appear, stop before any production signing. Revert Android.15 and keep Android.14 as the tested baseline.

**Release gate:** A successful build verifies packaging and regression tests, not a real GPU/FPS improvement. Proceed to permanent signing and publication only after the owner reports a hardware PASS.
