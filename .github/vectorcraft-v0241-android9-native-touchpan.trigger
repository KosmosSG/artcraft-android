VectorCraft v0.24.1-android.9 native glass two-finger canvas pan directional correction TEST ONLY.
Published exact baseline: vectorcraft-v0.24.1-android.9 tag at 9beff78fd24b59e806f65424f9ee6443943d2901.
Root cause: native winit emits MouseWheel PixelDelta for two fingers and suppresses individual Touch. Previous egui multi_touch change never ran. Mark actual glass-pan packets and correct only the canvas wheel sign; original trackpad and menu routing unchanged.
Diagnostics: vc_native_glass_twofinger_pan_packets and vc_canvas_glass_remap_events.
No Android.10 JNI typing experiment. No new text edits.
Disposable builder-signed ARM64 APK, separate label VectorCraft Glass Test and candidate application ID; no permanent signing, publishing, overwrites or merge.
