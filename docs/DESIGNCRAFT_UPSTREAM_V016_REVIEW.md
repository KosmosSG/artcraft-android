# DesignCraft official v0.16.0 — source-lock and Android 4 GiB preservation review (2026-11-02)

**Scope:** Review-only, stacked on DesignCraft 4 GiB font-scanner draft PR #98. No source port, new APK, signing, merge or release is claimed.

## Verified official source
- Official stable tag: https://github.com/storytold/designcraft/releases/tag/v0.16.0 (2026-11-01 19:32:27 UTC; not draft or prerelease).
- Direct tag commit: `1fe8885bda7451263879cfbb256b9a3d46c411bf`. Root Cargo workspace version `0.16.0`, Rust MSRV `1.95`, repository `storytold/designcraft`.
- Read-only provenance helper: `python3 tools/designcraft/verify_v016_source.py /path/to/clean/tagged/designcraft`; no checkout, build, signing or publishing is performed by this helper.
- Review upstream Type menu and CJK command structure, File/Quit handling and shared craft-update check-result UI against Android native menus and updater.

## Preserve tested Android behavior
- Preserve the publicly listed DesignCraft v0.12.0-android.9 APK and its stated 4 GiB recursive shared-font scanner, 5,000-file/folder refresh bounds, 64 MiB/font cap, TTF/OTF/TTC support, import success/error feedback and font catalog refresh. Public android.9 release asset SHA-256 is `bf74cf217c989a951303d7d5131b980871699335d429e523e50c10f310929162`; this is asset metadata, **not independent proof of internal scanner behavior**.
- Preserve Android-only SAF permissions, menus, Esc and D/C/S shortcuts, approved Dc launcher/adaptive artwork, updater GitHub APK channel and `com.artcraft.designcraft` package identity.
- Existing v0.14 host compatibility PR #89 does not prove v0.16 source/API compatibility. Avoid overwriting Android-only changes.

## Blocked gates
1. Port upstream v0.16 source and review dependency/API changes on an isolated integration branch without changing existing published APKs.
2. Pass host/type/menu/font tests and Android integration checks. Compile an ARM64 debug test APK only when explicitly authorized, preferably locally on HONOR Linux Lab to conserve Actions minutes. No quota-failing auto-build retries.
3. Verify exact APK SHA-256, ABI, package, monotonic versionCode, fonts, updater and approved assets.
4. Testing: Android APKs must be signed, but use the standard disposable **debug key** only. Original production keystore and GitHub signing secrets are NOT needed for the development APK. If replacing android.9, first export/backup all important local data, then uninstall android.9 to avoid signature mismatch; app-private state can be deleted.
5. Require HONOR MagicPad 4 acceptance of the **debug-signed** APK and all requested feature checks. Only after debugging is done, prepare a separate production candidate signed with the owner's original permanent DesignCraft key; verify signing certificate and require explicit owner merge/publication approval. No private Actions signing, auto-merge, release/tag or Latest change.

This is a source provenance staging PR, **not** a v0.16 Android integration or new installable APK.

## Reference-feature parity review (2026-11-02; no device verification)

Reference: `MostafaXS1/artcraft-android` changelog and builder, evaluated against this branch. These labels describe **source presence**, not working v0.16 Android functionality. Every feature needs compiled APK/device verification before release.

| Requested feature | Current DesignCraft v0.16 integration status |
| --- | --- |
| Automatic document save and crash recovery | **Partial**: DesignCraft-specific recovery folder, previous-recovery open and guarded save hooks added; periodic dirty-document autosave and SAF original-file synchronization not yet validated. |
| Auto-build on commit | **Available as opt-in**: CI remains configured, but expensive automatic ARM64 builds are disabled at owner's request to save monthly quota. No signing/publishing job. |
| Save and restore sessions | **Partial**: UI/preferences persist and recovery hooks added; restoring complete open-tab/workspace state not verified. |
| Two-finger scrolling | **Unverified / pending**: patched shared winit supports mouse/trackpad wheel, not proof that touch-screen two-finger pan works. |
| Better UI scaling on mobile | **Partial / pending**: existing builder has density-based scaling logic; v0.16 app API and HONOR tablet behavior not validated. |
| GPU acceleration | **Pending runtime validation**: wgpu renderer configured in launcher; cannot claim acceleration without Vulkan/GLES runtime diagnostics and device test. |
| Finger hold = right-click | **Not confirmed**: mouse right-button translation exists; finger long-press -> secondary click requires a distinct gesture mapping and canvas test. |
| Adaptive app icons | **Existing suite support; pending APK check**: preserve approved DesignCraft Dc artwork and packaged adaptive icon layers. |
| Adaptive cursor | **Not confirmed**: pointer-move events supported for hardware mouse; Android pointer icon changing by egui hover state not yet verified. |

**Build blocker identified:** upstream v0.16's `craft-dialogs` transitively needs `rfd 0.17`; previous Android vendoring check looked only for literal direct `rfd::` calls. The builder now opts into the existing vendored Android-compatible `rfd` when `-designcraft-v016` is used. This is a *source change only* until the experimental ARM64 job passes. Native `rfd` dialogs in the compatibility vendor may return cancel; the app's SAF bridge must be checked end to end before releasing.

Release gates: no automatic signing, no auto-merge, no publish, no change to Android.9, no claims of parity until hardware testing.

## Debug-first, quota-conserving test policy (owner decision, 2026-11-02)

- **Do not use original DesignCraft signing certificate** for the next ARM64 tablet testing cycle. Use an Android **debug-signed APK** (automatically signed by a disposable debug key at debug packaging). Debug APK != unsigned APK; Android rejects fully unsigned packages.
- **Owner accepts uninstalling the current Android.9** before installing the debug-signed APK, because the package name remains `com.artcraft.designcraft` but its signature changes. Warn and back up documents, fonts, preferences, app-private and SAF-related state before uninstalling. Debug-signature upgrades cannot replace production-signed installs in place; returning to production may require uninstalling debug app again.
- **No automatic GitHub Actions runner minutes for routine PR/branch commits** on this DesignCraft review workflow. To deliberately run source checks, a review-branch commit message must include `[designcraft-ci]`. To deliberately run the expensive debug ARM64 build, it must include `[designcraft-debug]` (or use `workflow_dispatch` when GitHub makes the workflow manually runnable, noting dispatch eligibility on default branch).
- Prefer building/debug-signing locally in the user's HONOR Linux Lab to minimize GitHub Actions usage. If local toolchain cannot compile, seek explicit user approval for a **single** GitHub debug build; do not make recurring quota-draining compilation retries.
- Debug builds are for device evaluation only; do not publish them as GitHub Releases, alter update channels, mark Latest, use production secrets or claim certificate continuity. A production release still requires original-key signing and separate user approval.
