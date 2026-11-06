# PDFCraft Android.11 trackpad candidate

Protected release: pdfcraft-v0.12.1-android.3, ba604057f77eb0ae45dac85914280121d0e9eb12.
Development base: 0b229e3dc9373a39cf750b1ebc17848a76ab2eb6 (android.10), successful Actions 42041590647.
Upstream stays pinned to v0.18.0, 3936f93a1479366a951206fc6d3094680fe2d3dc.
Candidate package: com.artcraft.pdfcraft.scrolltest; disposable signer only. No public release.

## Evidence and limits

The initial recording was mistakenly identified as Acrobat because of the similar interface. Subsequent recordings show the PDFCraft Android diagnostics. The initial recording contains no input timestamp trace and cannot establish a physical-device root cause or input-to-photon latency.

Confirmed source defects:

* android_trackpad_patch.py previously selected precision on EACH event's fractional remainder. A SOURCE_MOUSE sequence 0.25, 1.0, 0.0, -1.0 switched between PanGesture/Point and the stock LineDelta path. PDFCraft's canvas/wheel_boost.rs accelerates Line events, while canvas.rs read_wheel bypasses easing for Point events. This yields inconsistent distance and response within one gesture.
* The old adapter emitted End on any single-pointer zero-axis/hover sample following axis scrolling. canvas/fling.rs interprets End as finger lift and can launch client momentum. Native zero-axis samples are not proof of finger lift. Android-provided momentum could be compounded with this client fling.
* Cancel previously became End. Per-event axis clamps also discarded real displacement at high event deltas.

Changes: keep precision classification within a timestamped/device-scoped stream; recognize mouse-source finger tools; retain exact finite axis distances; let Android own momentum for axis streams without invented Start/End; retain real phases for raw two-pointer gestures; map cancellation to Cancel; preserve click-and-drag by bypassing gesture interception while buttons are pressed. Existing pinch lock, touchscreen paths and cursor integration remain.

An initial integer mouse-source event with no finger/tool/gesture evidence remains ambiguous and takes the ordinary mouse path. Precision evidence is retained until a device change, timestamp reversal, explicit reset or 250 ms gap. No velocity or sensitivity multiplier has been added.

## Rendering audit

Upstream raster.rs uses background RenderPool workers and CPU hayro rasterization. canvas.rs plan_renders already reuses cached page/tiles, prefetches neighboring rows and defers expensive sharp re-renders while moving. WGPU composition remains enabled. No evidence yet justifies replacing these mechanisms or claiming full GPU rasterization. No Vulkan present-mode changes are made without device measurements.

## Diagnostics

Optional native atomics capture event counts, source/action, Android nanosecond event timestamps and axis-event frequency. Native dispatch-to-UI completion is measured with Instant, not mislabeled as input-to-photon. UI interval mean/variation, pass rate and intervals over 33.3 ms are reported separately from CPU UI work. These are UI passes, not measured display FPS or dropped display frames. Java diagnostics include classification when available; the native binding does not expose it. GPU upload/present and raster-worker durations are explicitly unavailable in this candidate. Disable measurements to bypass native instrumentation.

## Validation

Source tests exercise the real patch generator, preserved D/C/S/tool/IME/font/menu/cursor contracts and approved branding. Rust replay tests cover fractional/integer/zero sequences, timestamp rollback, device changes, idle and reset. CI also compiles the ARM64 app, tests keyboard/PDF objects and verifies package/version/ABI/signature. Source-string contract checks do not prove real gesture behavior.

## Device test

Keep stable PDFCraft installed. Install only the separate scrolltest package. Open a copy of a PDF, enable performance measurements, close diagnostics, and compare slow/fast vertical and horizontal gestures. Check zero-delta pauses, lift, cancel, reversing direction, pinch, selection drag, touch scrolling and ESC/D/C/S. Reopen diagnostics and record values. Check open/edit/save fidelity, fonts and cursor. Do not approve permanent signing until this exact artifact passes real-device testing.


## Android.12: native batched relative-scroll samples

Owner reports android.11 still stutters while touchscreen scrolling is smooth. In SVID_20261106_132947_1.mp4 near 46 seconds: native mouse/trackpad events 668; axis events 36; egui wheels 36; zoom events 0; last dispatch-to-UI 1.93 ms; UI CPU work 2.62 ms; mean active UI interval 22.30 ms and variation 33.66 ms. These values are snapshots, not proof that the GPU never stalls. The 1.2 events/s capture average includes idle time and is not the physical trackpad sampling rate.

The adapter drops all historical axis samples, reading only the latest one. Android explicitly defines AXIS_GESTURE_SCROLL_X/Y_DISTANCE as relative per sample and requires processing batched history:
https://developer.android.com/reference/android/view/MotionEvent#AXIS_GESTURE_SCROLL_X_DISTANCE

Android.12 exposes the already-supported borrowed NDK history iterator only in PDFCraft's staged NativeActivity dependency, then accumulates historical and current relative axes exactly once. Absolute touchscreen coordinates are not accumulated; the working touch path is unchanged. A batch whose current sample is zero can still contain movement. Fractional precision evidence is retained even if samples sum to an integer. Summation uses f64 and rejects nonfinite samples. No added easing, velocity, sensitivity or momentum multiplier.

The recording does not prove that this device supplies nonempty history. New counters report total historical samples and nonzero scroll samples recovered; native within-burst gap mean/max and maximum dispatch-to-UI completion help distinguish sparse delivery from occasional frame stalls. Device validation is still required. No rendering-path change is justified by the current evidence.

Candidate 0.18.0-android.12, versionCode 16781836, separate package com.artcraft.pdfcraft.scrollhistory, disposable key. Different test identity avoids signature conflict with android.11; production remains untouched. Added native history API guards and Rust replay tests for partition-invariant distance, zero-tail batches, sign reversals, integer sums with fractional inputs and invalid samples.


## Android.13: offline Scan & OCR models

Owner requested the OCR addition from MostafaXS1/artcraft-android v0.5.0, source tag commit 52308fbcb26d8d8625f35fc1f048813f8e1e12a8. Only model packaging and startup availability are integrated; the builder is not replaced. PDFCraft remains pinned to official 0.18.0 with the android.12 history fix and existing Android features.

The two upstream ONNX files are fetched using immutable expected SHA256 values already present in official ATTRIBUTION.toml. Missing or changed files fail the build. Both models, their attribution and unmodified CC-BY-SA-4.0 text are packaged and checked inside the compiled APK. Licence text was retrieved from Creative Commons' own repository at https://raw.githubusercontent.com/creativecommons/creativecommons.org/master/docroot/legalcode/by-sa_4.0.txt and matches upstream's pinned 28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5 checksum.

Startup copies assets to internal app-private storage via temporary files, verifies checksums before renaming, and sets PDFCRAFT_MODELS only after both models pass. No model download runs on the tablet. Failures are nonfatal and shown in Android tools. The existing Scan & OCR workflow handles recognition and the invisible searchable PDF text layer. English is the documented model language; no Chinese or multilingual recognition claim is made.

CI runs pdfcraft-ocr unit tests with models installed, rejects the upstream recognition test's missing-model skip, and verifies both model hashes inside the APK. Device acceptance still requires an image-only PDF: recognize English text, search/copy it, save a copy, reopen and verify text/image fidelity. OCR adds approximately 12 MB of raw model data plus extracted private copies, and can use CPU/RAM during recognition. Trackpad smoothness remains unverified.

Candidate: 0.18.0-android.13 / 16781837 / com.artcraft.pdfcraft.ocrtest. Disposable signer, separate installation, Actions artifact only. No production keys or release publication.
