# WordCraft v0.17.0 Android integration — preservation gate (2026-11-10)

Status: **UPSTREAM REVIEWED; SOURCE PORT NOT YET VERIFIED; DO NOT RUN CI OR RELEASE.**

## Verified immutable inputs
- Protected published Android tag: `wordcraft-v0.15.2-android.11` -> `af5b31029902bb1cf7f9714521c1e1bb84db76a5`.
- Dedicated integration branch was created as a descendant of this exact tag. Preserve this ancestry.
- Official Storytold v0.17.0 tag -> `5574b32600aa7d782c64f5a6c6bb24696152220d`.
- Baseline Android.11 workflow currently checks out Storytold **v0.15.2** at `edfea68101220c9bdc4b2b0ccf4acd9612bedb6e`. It is not a v0.17.0 build.
- Official v0.17.0 Cargo workspace declares `rust-version = "1.95"` (check installed toolchain before expensive Android setup).

## Upstream changes to migrate selectively
The official v0.17.0 release includes DOCX/ODT/RTF and legacy DOC import fixes, Save As filename suggestion, scrolling/scrollbar fixes, RTL and typography improvements, page-layout refinements, and UI changes. Assess each against Android source anchors; do not bulk cherry-pick the entire upstream repository history.

## Android preservation contract — stop on any regression
- App identity: keep production `com.artcraft.wordcraft` unchanged; a candidate must use a distinct `com.artcraft.wordcraft.*` package and disposable signing key.
- Preserve Wc branded compact menu; Appearance's single System/Light/Dark theme selector (no duplicate Dark Mode); in-app updater; fonts import/SAF shared folder/refresh; file associations; document autosave/recovery.
- Preserve physical keyboard shortcuts, ESC, IME composition/focus, Ctrl+W repeated D/C/S, Ctrl+Q and Save As (including Ctrl+Shift+S where implemented).
- Preserve pressure enabled by default, stylus hover and palm rejection; never drop pen ink when an actual stylus is drawing.
- Two-finger touchscreen and physical trackpad pan/pinch must suppress text selection and accidental ink; retain one-finger text selection and ensure pan-first gesture does not misclassify as zoom.
- Preserve GPU rendering fallback; target adaptive pacing up to display-available 165 Hz, not a forced 165 FPS.

## Migration/build gate
1. Create v0.17-specific compatibility tests for Android patch anchors; run them **before** installing the SDK/NDK or invoking Cargo/Gradle.
2. Pin official upstream commit and verify tag, builder SHA, toolchain version and dependency integrity.
3. Apply existing Java/Rust/SAF/stylus/gesture overlays to a disposable checkout; resolve upstream API changes without changing suite main or any other app.
4. Assert package, ABI=arm64-v8a, candidate version, no permanent key use, branded icon, updater URL, gesture and shortcut source guards, asset size and document-preservation tests.
5. Once all cheap tests pass, trigger one optimized ARM64 candidate build; upload only a disposable-signed separate-install APK, SHA256SUMS, and verification metadata; retain artifacts for device testing.
6. Test physical HONOR MagicPad 4 gesture and stylus behavior, document round trips, ESC / Ctrl+W D/C/S / Ctrl+Q, Save As and recovery.
7. **STOP**. No merging, permanent signing, publishing or changing production package/signature before explicit approval.

## Current blocker
The current v0.15.2 candidate workflow includes version-specific Cargo manifest replacement and compile steps; changing only the upstream commit would break its old-version assertions and could consume CI minutes. A verified v0.17 patch/workflow and actual candidate APK have **not** yet been produced.
