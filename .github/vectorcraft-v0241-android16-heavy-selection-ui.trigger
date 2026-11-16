Run one disposable VectorCraft v0.24.1-android.16 ARM64 test APK build. BASE: successful Android.14, not Android.15. Optimize selected nested group UI with cached anchor counts, 2048-point visual cap and skip unused selection meshes; run source/typing/stylus/IME regression gates; temporary signing only, separate package, artifact only, never publish or modify stable release.

Retry after source-guard preflight: Android.13 staged regression now explicitly recognizes Android.16's Android-only 2048 selection cap while retaining desktop 100000 and Android.14 pan. Fixes post-compile assertion on canvas/outline.rs; no application source changes.

Retry after post-compile Android.13 staged guard correction: original 100000-anchor literal must remain once in desktop cfg while Android.16 uses 2048 Android-only. Source-only preflight passed; no application changes.
