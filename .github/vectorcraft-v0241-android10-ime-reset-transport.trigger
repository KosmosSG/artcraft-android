VectorCraft v0.24.1-android.10 disposable signed ARM64 TEST only
Baseline: published tag vectorcraft-v0.24.1-android.9
Fix missing vendor native-to-Java reset handoff; preserve stale IME fence and editor identity checks
Dedicated source probe and staged validation prevent silent omission
No production signing, merge or release modification
Retry 2: accept only the exact pre-staged native winit reset bridge while fresh android-activity JNI glue is repatched; add mixed-stage regression probe. Disposable-signed ARM64 TEST only.
Retry 3: fix Rust E0592 duplicate vc_reset_ime definitions across staging and packaging; assert exactly one JNI reset method in both android-activity source files and winit. Disposable ARM64 TEST only.
