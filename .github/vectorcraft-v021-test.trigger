VectorCraft v0.21.0-android.5 — source-gated ARM64 test APK only
Owner-approved Android-only continuation of stable-feature-preserving v0.21.0 integration.
Black startup fix: AndroidX core-splashscreen 1.0.1, setKeepOnScreenCondition until JNI after first native paint requests Java PixelCopy confirmation of nonblack SurfaceView pixels; 20-second fail-safe.
Font fix: persistent BFS queue of SAF document IDs / nested folders with atomic checkpoint; 128-font, 64 MiB batches chained automatically; up to 5000 file IDs and 4 GiB data; unknown SAF sizes validated by font header.
Report each batch for background Rust FontDb updates without UI blocking. Preserve previous fonts and approved Vc icon, menu, keyboard, updater controls and stable data.
Run Python and JVM test gates before Android SDK/Rust; do not compile if any fail.
Use only com.artcraft.vectorcraft.test with disposable test signer. No production key, no signing approval, no GitHub Release publication.

Recheck source guards: migrated offset scan and native activity AndroidX splash test declarations. No permanent signing.

Replacement Android.5 build: correct android.view.PixelCopy Java SDK 35 import; assert javap availability prior to ARM64 Rust compilation. Retain disposable test signing and preserve approved features.
