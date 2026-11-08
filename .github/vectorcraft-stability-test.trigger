VectorCraft v0.21.0-android.19 — MOSTAFAXS1 LATEST COMPATIBILITY REFERENCE — TEST ONLY
Source version: official Storytold VectorCraft 0.21.0 immutable sha 11862f61198c8f62c0b22b6c9a331cc5950ac98d.
Android builder: MostafaXS1/artcraft-android main SHA 52308fbcb26d8d8625f35fc1f048813f8e1e12a8, dated 2026-11-05 (shortcut/IME/gestures). PINNED; do NOT overwrite user customization.
Owner: KosmosSG/artcraft-android; branch investigation/vectorcraft-android10-20261105. Existing approved Android features, shared SAF fonts up to 5000/4GiB, update checker, menus/icons, adaptive pointer, touch/trackpad, Save/ESC/Ctrl+W/Q, keyboard, persistence, canvas and SAF preserved.
Android.18 FAIL on HONOR MagicPad 4: same launch delay/black screen; V/C tool shortcuts, Ctrl+W > ESC > D/S/C, touchscreen pinch/pan, trackpad pinch/pan failures. New SVID_20261109_012721_1.mp4 reviewed.
Android.19: selectively port Mostafa's View.GONE and nonfocusable IME host outside editing while keeping all owner c/p/f/d/a protocol. Immediate Java event-loop wake when modal key is queued, rather than after ESC. PixelCopy(Window) screen-paint verification rather than nonexistent native SurfaceView (previous diagnostic 0 frames). Retain existing upstream canvas gesture changes from Android.18. Builder now newest 2026-11-05 SHA, giving actual recent native input/gesture backend instead of old Nov-05 builder.
Preflight MUST reject any mismatch before costly ARM64 compilation. Separate com.artcraft.vectorcraft.test package; disposable key only. Never publish/tag/merge or touch production signing.

Cheap source-preflight retry #1: all generated overlay anchors applied correctly. Adjusted static regression to check Android.19's modal queue wake instead of helper defined in Android.15. SHA fc1b89e7882d20b570d711958b459bb5ca20ea63. Test-only.

Builder-compatibility retry 2: Mostafa main vendor already defines API-safe native MotionEvent classification() and winit consumes it; previous owner patch needed only on older builder. Idempotent guard verifies latest implementation and skips obsolete overlay. Commit 1fcb66ef01bd107717dc6734881b7bada17618dc; avoid touching production keys.
