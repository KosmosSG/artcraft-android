# PDFCraft Android.11 trackpad candidate

Protected release: pdfcraft-v0.12.1-android.3, ba604057f77eb0ae45dac85914280121d0e9eb12.
Development base: 0b229e3dc9373a39cf750b1ebc17848a76ab2eb6 (android.10), successful Actions 42041590647.
Upstream stays pinned to v0.18.0, 3936f93a1479366a951206fc6d3094680fe2d3dc.
Candidate package: com.artcraft.pdfcraft.scrolltest; disposable signer only. No public release.

## Evidence and limits

The supplied 22.57-second recording appears to show Adobe Acrobat, not the PDFCraft diagnostics screen. It contains no input timestamp trace. It cannot establish PDFCraft's physical-device root cause, GPU frame time or input-to-photon latency.

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
