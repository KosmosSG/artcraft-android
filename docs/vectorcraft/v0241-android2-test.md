# VectorCraft v0.24.1-android.2 — isolated test candidate

Protected baseline: `9b031d503b1c5073b7b88bf80ca498d7f970563b`, successful run 43259196493.
Official upstream remains pinned to `f4922aa7ac99a4f6d56fc68a83a44945207ec610` (v0.24.1).
Builder remains pinned to `52308fbcb26d8d8625f35fc1f048813f8e1e12a8`.

## Changes and evidence

The baseline raw wheel capture forwarded PointerMoved while consuming the press, and its visual Area was noninteractive. Underlying tools therefore retained pointer hover. The candidate consumes pointer movement, touch, relative motion, button and gesture events during the wheel session, including the accepting contact through release. A frame-local flag guards canvas dispatch and drains native pen samples. It is recomputed every input pass; no mutex, global modal latch, or timeout is introduced. The customizer retains egui input while excluding document input. Upstream floating-panel layer hit-testing is retained.

Preview and real wheel call the same painter with the actual layout, size and opacity, including branding and shadows. Tablet controls use aligned grids beside the preview. Narrow windows keep sliders and preview above scrollable assignments. Preview hover is visual only. Preferences retain the legacy eight-value and current ten-value format.

The baseline finishes its Activity after eframe returns but leaves process-wide native state alive. The candidate terminates its own process only after confirmed upstream quit, persistence in on_exit, and NativeActivity.onDestroy returning. Backgrounding, rotation, file pickers and cancelled quit do not take this path. Existing IME epochs, document fences and first-edit rebind remain. This addresses process reuse as a possible contributor; the recording does not establish a measured root cause of the device stall.

The fixed 120ms cover delay is replaced with a UI-frame callback. A one-shot asynchronous PixelCopy reports whether a buffer is available; it does not gate startup and does not retry. UI traversal, successful buffer observation and main-looper readiness are reported separately, not treated as equivalent proof of responsive canvas.

## Build validation

CI runs source regression checks, generated wheel behavioral tests (hover, exactly-once action, release after Type/document transition, repeated cancellation, preference roundtrip and headless preview), existing input routing tests, and upstream engine text/UI typing/IME suites. Android compilation verifies Java and Rust targets. APK verification checks ARM64 only, signature differs from production, package/version, ZIP integrity and SHA-256. Signature and package reports are retained in the artifact.

Package: `com.artcraft.vectorcraft.candidate_v0241a2`. This installs alongside production and the previous `.test` APK; its settings are separate. Do not uninstall either existing app or clear data. Production Java/JNI namespace remains unchanged. Only a disposable signing key is used; no release is published.

## Required HONOR MagicPad 4 tests — not verified by CI

1. Enable wheel; open Customization. Adjust 75–140% size, 30–100% opacity and every action; check preview and persisted settings after restart. Reset and scroll dropdowns with trackpad, touch and pen.
2. Over existing objects, open wheel, hover every sector, tap once, cancel, and resume drawing/selection. Repeat 20 times. No underlying highlight, selection or movement should occur.
3. Wheel → new document; wheel → close document → new document. Test ESC, V/T/H, Ctrl+W D/S/C, touch/trackpad pan/pinch and pressure/hover cursor.
4. Ctrl+Q → relaunch ten times. Type in a new document and imported Crafticon V2.ai each time; close imported document and create another. Repeat five cold starts. Record delays or ANRs.
5. Confirm font import/shared library/refresh, Appearance and updater behavior.

If delayed, collect logcat tags VC_LIFECYCLE2, VC_QUIT4, VC_STARTUP, VC_MAIN7 and VC_IME12. Compare process IDs across confirmed quits. The manual diagnostic report includes cumulative wheel-consumed events and canvas-input frames, without coordinates or document content. No successful physical-device result is claimed.
