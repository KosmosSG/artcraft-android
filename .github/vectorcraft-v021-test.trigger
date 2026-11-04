VectorCraft v0.21.0-android.7 — one owner-approved disposable-key ARM64 test APK
Owner device feedback: Android.6 startup black remains; physical trackpad menu scroll stutters; font scan works; physical tool shortcuts and D/C/S intermittently fail.
This revision targets demonstrated keyboard input issues and wheel event batching:
- Modal Save Changes D/C/S recognizes key press even when Ctrl from Ctrl+W remains latched; never steals keys from a focused text field.
- Reset left/right Ctrl/Alt/Shift state when Android native window regains focus and after Type editor Escape / Ctrl+W handoff.
- Restore hardware keyboard focus to actual native SurfaceView instead of first random overlay child.
- Eased menu-only trackpad wheel events at 16ms intervals; preserve ALL touch ScrollSource and canvas wheel events.
- Preserve Android.6 PixelCopy splash instrumentation, but do not claim black-screen issue resolved without tablet verification.
- Preserve approved 5000 font / 4GiB background SAF scanner, launcher, updater and menus.
- Full source-level and JVM gates BEFORE expensive Android SDK/native build.
- Only separate com.artcraft.vectorcraft.test test package, ARM64, disposable signing. No permanent signing, release or stable changes.
