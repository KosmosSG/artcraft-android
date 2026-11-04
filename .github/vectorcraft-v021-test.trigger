VectorCraft v0.21.0-android.8 — one owner-authorized ARM64 temporary-signature test build
Reference: MostafaXS1/artcraft-android/releases/tag/v0.2.0, Adaptive Cursor ONLY.
v0.2.0 mapping: egui Text -> Android I-beam, PointingHand -> hand, Crosshair, move, grab and resize arrows.
Implementation: Android NativeActivity JNI bridge vcSetAdaptivePointerIcon updates real native SurfaceView only when egui cursor type changes. Reset after surface focus changes.
Do NOT transplant the older builder, overwrite touch/keyboard event routing, or touch existing startup and popup scroll paths.
Preserve all tested VectorCraft Android.7 fixes including Ctrl+W D/C/S, keyboard focus recovery, icon, shared font scanner (5000/4GiB), updater, SAF.
Automatic source/JVM guard tests before native build; Android ARM64 com.artcraft.vectorcraft.test only with disposable key.
Do not use permanent signing or modify published stable VectorCraft.
Do not create/publish any GitHub Releases. Provide APK artifact for tablet testing if checks pass.
