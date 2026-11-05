VectorCraft v0.21.0-android.9 — ONE temporary-signed ARM64 test APK
Owner video SVID_20261105_153754_1.mp4 from HONOR MagicPad 4:
PASS — V/T/P tools working (preserve).
FAIL — D/C/S keyboard while original Save Changes modal is open.
FAIL — Ctrl+Q not finishing Android application.
OPEN — Vc startup screen still shown for several seconds. Do not claim solved, retain branded safety cover and startup diagnostic.

Fix D/C/S: physical raw egui Key press for this modal only; ignore stale Android IME text-field focus and popup-open gating. Preserve original Save/Don't Save/Cancel callbacks.
Fix Ctrl+Q: convert physical chord to upstream app.quit, which shows unsaved prompts; only on app.ui.status=="quit" call JNI vcFinishAfterQuit -> Activity.finishAndRemoveTask. Cancel must not exit. No data deletion.
Preserve existing adaptive cursor Android.8, keyboard tool shortcuts, 5000 font /4 GiB SAF scanner, updater, trackpad scroll, icon/splash.
Use tests BEFORE expensive compile. Build only disposable signed ARM64 com.artcraft.vectorcraft.test. Never touch signing key or publish.
