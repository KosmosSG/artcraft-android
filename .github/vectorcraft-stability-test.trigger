VectorCraft v0.21.0-android.24 — isolated FIRST FRAME + MENU TRACKPAD + PINCH trial on HONOR MagicPad 4.

Confirmed Android.23 device FAIL: startup black/unresponsive, menu stutter, trackpad two-finger pan/pinch stutter and accidental selection. Keyboard V/T/H/ESC and Ctrl+W D/S/C PASS, protected unchanged.

Branch-only patch source: tools/vectorcraft/patch_android24_startup_menu.py; tests: tools/vectorcraft/test_vc_android24_overlay.py; workflow: .github/workflows/vectorcraft-android24-test-apk.yml.
Changes: first-buffer-aware cover removal after Rust first UI signal (bounded nonblocking PixelCopy, max 2.8 seconds); per-popup wheel factor 0.90 without touching touchscreen navigation; final vendored winit trackpad pan packet limit 160 physical pixels, pinch factor 0.75..1.33 so MagicOS batched packets are not silently discarded. Existing two-finger selection suppression is retained.

Run cheap Python+Rust source/backend preflights before expensive NDK and ARM64 builder. Pinned upstream SHA 11862f61198c8f62c0b22b6c9a331cc5950ac98d and builder SHA 52308fbcb26d8d8625f35fc1f048813f8e1e12a8. Build ARM64 only, package com.artcraft.vectorcraft.test, v0.21.0-android.24 / code 16783384, disposable signing; never use production key or publish/merge/tag; produce private artifact for tablet test. GitHub Actions workflow must fail closed on source drift.
