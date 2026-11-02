# VectorCraft Android 0.20.0 compatibility development — 2026-11-02

## Source-of-truth and non-destructive baseline

- Published Android release: `vectorcraft-v0.14.0-android.13`, published 2026-10-31. Its tag resolves to `9d5197b30a53071841a7592975e16757c41f22d9`. Published signed APK must not be replaced.
- New development branch: `development/vectorcraft-v020-android14-20261102` forked from `feature/vectorcraft-4gib-font-scan-20261030` at `321ba2097362a3916111845bfa6740d479796412` (PR #97). This preserves the more complete 4 GiB font-scan development code and existing UI/font/updater patches; the published release tag itself does **not** contain every such newer source change.
- Official upstream stable release at review date: `storytold/vectorcraft v0.20.0` (`5628de96f866185d8eb289b167b89691f213c0c3`, released 2026-11-01). Official main is newer, and must be evaluated separately rather than silently substituted into a reproducible candidate.
- Android builder reference `MostafaXS1/artcraft-android` is pinned for the compatibility check at `fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`. Do **not** overwrite the user-owned, more complete VectorCraft Android adapter with the generic reference adapter.

## Port status

This branch has a reference-tested improvement to the vendored Android winit input classifier:
- Correctly interpret Android's combined source bitmask (including touchpads that report SOURCE_MOUSE | SOURCE_TOUCHPAD).
- Use the device/tool to distinguish a smooth touchpad scroll from discrete mouse wheel notches rather than switching units at an arbitrary scroll magnitude.
- Preserve the existing mouse right-click and stylus/touchscreen event paths.
- Run a host-only regression suite with `rustc --edition=2021 --test tools/vectorcraft/test_device_kind.rs`.

This **does not** yet implement every touchscreen two-finger gesture, long-press right-click, adaptive cursor, or v0.20 native integration. Source and physical-device verification are still outstanding.

## Upstream and Android gates

The branch-only `vectorcraft-v020-android-compat.yml` workflow:
1. Runs existing VectorCraft Android tests and touchpad regression tests; checks Android package `com.artcraft.vectorcraft`, SAF, fonts, updates, IME, shortcuts.
2. Checks out immutable upstream `v0.20.0` and the Android reference builder.
3. Overlays only our reviewed Android adapter, runs strict menu/updater/unsaved-changes patches, and attempts an ARM64 Rust `cargo check`.
4. Uses read-only CI permissions. **No release publication, no signing keys, no uploaded APKs, and no automatic merging.**

A green source check only establishes initial compile compatibility. Follow up with runtime integration and validation of document autosave/recovery, session restoration, 2-finger touch scrolling, long-press/right-click, scaling, GPU diagnostic or acceleration feasibility, existing approved adaptive icon and file suffix behavior. Respect the difference between CPU canvas rendering and a wgpu UI adapter.

## Mandatory preservation and publication gates

- Existing SAF Open/Save and original document URI mapping; no data loss.
- Existing D/C/S unsaved-document modal, Escape/tool shortcuts, Ctrl+W and the contextual task bar.
- Existing 4 GiB bounded, nested SAF font scanning and TTF/OTF/TTC import, cache and feedback.
- Existing PhotoCraft-style update checking and stable/preview/startup controls.
- Current production `com.artcraft.vectorcraft` app ID, owned glossy Vc launcher/adaptive artwork, and the **original independent VectorCraft signing certificate**.
- Never assume a successful source compile means the new APK can upgrade the current production installation. Only after successful ARM64 APK packaging, permanent-signature verification, an increased versionCode, and user device testing may a draft release be considered.
- **Require the user's explicit go-ahead before publishing either a preview or stable release.** Do not run automatic publication workflows for this branch.
