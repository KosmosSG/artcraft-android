VectorCraft v0.23.0-android.2 focused Ctrl+Q ANR and pinch sensitivity ARM64 TEST ONLY
Pinned official Storytold v0.23.0 and approved Android.1 native gesture/IME baseline
Branch: fix/vectorcraft-v023-android2-quit-pinch-20261110
Draft PR #151; parent test draft PR #150
Changes: after upstream quit confirmed, native egui viewport CLOSE; Java finish ONLY after eframe loop returned
Pinch: prioritize API34 native pinch even when Swipe classification; subtle pinch confidence; intentional pan-to-pinch handoff
Preserve: Type, ESC, V/T/H, Ctrl+W D/S/C, smooth trackpad canvas scroll, popup scroll, fonts/updater/stylus
Version 0.23.0-android.2; code 16783902; com.artcraft.vectorcraft.test; ARM64; disposable test signature
One-shot CI; no merge, permanent signing, release tagging or publishing
