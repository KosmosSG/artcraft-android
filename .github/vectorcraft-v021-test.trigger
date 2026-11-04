VectorCraft v0.21.0-android.6 — one disposable-key-signed ARM64 regression test.
Owner video 2026-11-04: physical trackpad long menu scrolling is jerky; startup still perceived to expose black/native interval; some fonts still missing.
Changes:
1. Keep AndroidX splash and approved Vc brand maroon window background.
2. PixelCopy native SurfaceView requires 2 consecutive frames with both bright/light and dark UI detail (not cleared GPU surface) before hiding splash.
3. Android-only egui long menus: stable popup scroll state, 0.78 physical-wheel multiplier, 16ms repaint cadence when egui reports scrolling; retain existing Vulkan renderer.
4. Preserve previously approved launcher/menu, keyboard, dialog shortcuts, shared font BFS with 5000/4GiB, updater.
Run lightweight source/JVM tests BEFORE expensive Android SDK + ARM64 compilation.
Build only com.artcraft.vectorcraft.test; use fresh disposable key; never permanent sign/publish or overwrite stable APK.

Retry: updated old Android.5 test version marker and verified JNI bridge methods are in VectorCraftActivity, not VectorCraftExtras. No behavioral code changes.
