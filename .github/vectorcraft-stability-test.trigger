VectorCraft v0.21.0-android.16 UI-FRAME SAVE MODAL ARM64 DISPOSABLE TEST ONLY.
Branch investigation/vectorcraft-android10-20261105; source commit cb1da1d0e2888ed072b29a219f2bef723ee4f9a7.
Device HONOR MagicPad 4: Android.15 D and S actions recorded (D docs=1->0; S docs=1->1) but their visible outcome appears only after pressing ESC, even after exiting text mode first. C and touchscreen buttons work.
Correct route: queue S/D/C/Escape in raw_input_hook, apply exactly once at start of eframe::App::logic, bounded repaints 8x16ms; consume stale paired modal input without changing canvas/typing; trace Java SAF save picker stage and first-frame probe before early return; no usernames/typed text/path logging.
Preflight Python regression/source overlays before costly Rust/NDK compile. Original published app and all customizations protected. Separate com.artcraft.vectorcraft.test ARM64 APK, disposable signing. NEVER use production key, merge, tag or publish.
