# VectorCraft v0.23.0 Android.26 upstream integration (TEST ONLY)

**Base branch:** `investigation/vectorcraft-android25-reference-gestures-20261109` (`9b257e5209ccdc7bca437de6737c6a8c42eb0876`)

**Development branch:** `integration/vectorcraft-v023-android26-20261109`

**Official source:** Storytold VectorCraft release `v0.23.0`, immutable commit `5d0e892e2419f63bc0ea3c743ddff2e81e15fd3a`.

**Android builder:** MostafaXS1 ArtCraft Android `52308fbcb26d8d8625f35fc1f048813f8e1e12a8` (published v0.5.0 reference). Builder must not auto-update upstream during build.

## Changes under test

- Stage the complete pinned official VectorCraft 0.23.0 application source, including rendering, text, AI import/export, EPS, and editor improvements from 0.22.0 and 0.23.0.
- Preserve the Android.25 patch pipeline as a strict, fail-closed overlay instead of replacing tested Android Java, Rust adapter, or patched winit with unreviewed upstream Android input code.
- Allow 0.23.0 in the Android-only menu, adapter and save-changes patch guards. Exact content anchors, keyboard hooks and modal tests still gate each transformation.
- Keep the **published MostafaXS1 v0.5.0 native pan/pinch routing** restored by Android.25, with no experimental gesture fallback; do not reintroduce popup wheel attenuation.
- Retain Android.25 keyboard/IME, V/T/H, ESC, Ctrl+W D/S/C, fonts, icons, updater, frame timing instrumentation and splash safety checks.
- Build only `com.artcraft.vectorcraft.test` for ARM64 with a **disposable signing key** and a verification report. Never use or access the original signing key; do not publish a GitHub Release.

## Release gates

1. Verify immutable official and builder source SHAs and `0.23.0` manifest before SDK/NDK installation.
2. Run Python source-overlay tests, staged source preflight, native input tests, and Rust tests prior to full ARM64 compilation.
3. Verify package ID, ARM64 native libraries, version, certificate mismatch against stable, APK SHA-256 and verification.json.
4. **DEVICE TEST REQUIRED** on HONOR MagicPad 4: five cold starts (no black screen), native trackpad two-finger canvas pan/pinch (smooth and without accidental selection), trackpad popup scrolling versus two-finger touch, V/T/H after typing and ESC, Ctrl+W then D/S/C repeatedly, plus fonts, updater and stylus.
5. STOP at disposable signed test artifact. No permanent signing, merging, tagging or publishing without separate approval.

The workflow is trigger-file gated. A successful CI build confirms an installable test artifact, not device-level performance or a release.
