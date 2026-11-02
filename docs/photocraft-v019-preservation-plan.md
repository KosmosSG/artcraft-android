# PhotoCraft Android official v0.19.0 upgrade — isolated preservation track

Status: **development / source-compatibility audit only (2 November 2026)**.
Do **not** describe this stage as having integrated autosave, sessions or new gesture handling until compiled and device-tested.

## Exact baselines
- Published owner-tested Android release: photocraft-v0.14.0-android.4, Git commit 3af883c9db9d57d1b1641629707c2927176b484a.
- Stable Android production certificate V2 SHA-256: EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936. Never regenerate or replace.
- New official upstream PhotoCraft release: v0.19.0 (published 1 November 2026), exact commit 2df9f807702a935184041355a86405380bda8274.
- Android reference: MostafaXS1/artcraft-android, main as inspected 2 November 2026. Its v37 changes were dated 20 October 2026.
- Review base branch: release/photocraft-v0.14.0-android.4-preserved, **from published release**, not from main.
- Working branch: feature/photocraft-v019-android-preservation-20261102.
- This track is separate from draft PhotoCraft AI PR #93 and does not touch existing release tags or production releases.

## Feature requirements and acceptance gates
| Requested feature | Current evidence / next required work |
| --- | --- |
| Preserve PhotoCraft editing, project data and existing SAF save/open | Frozen published adapter, runtime, Java and build bridge; verify open, edit, save to same provider URI and reopen on device. |
| Import fonts, 4 GiB recursive 5,000-file scanner, system fonts | Existing production features; recheck discovered families, subfolders, persistency and import feedback. |
| ESC/C-Y-N/D-C-S, physical shortcuts and IME | Do not replace NativeActivity with reference GameActivity wholesale. Test hardware keyboard and Text editing focus on HONOR MagicPad 4. |
| Existing local U2NetP AI (experimental) | Preserve existing AI integration and sidecar contract, do not bundle model weights or enable remote uploads. |
| Existing Vulkan/WGPU and GPU information | Preserve renderer setup and CPU fallback; recheck actual GPU adapter after build. |
| Auto-save, crash recovery and sessions | Inspect v0.19 upstream RecoveryStore/Services APIs. Integrate through PhotoCraft-specific adapter, with lifecycle flush, recovery consent and non-destructive test. Not yet implemented. |
| Two-finger scrolling and adaptive cursor | Audit reference winit patches against owner's vendor and keyboard tracker; test touch, trackpad, mouse and pen independently. Not yet ported. |
| Mobile UI scaling and long-press right-click | Choose Android-safe gesture thresholds; never steal drawing/pen events; test at both tablet and phone dp sizes. Not yet ported. |
| Adaptive launcher icons | Reuse exact previously approved blue Pc icons; no new generation or double masking. |
| Duplicate file extension | Existing PhotoCraft Java stages names using stem + ' (n)' + extension, so no duplicate-extension rewrite needed. Test Save As and export with actual SAF DocumentsUI to confirm. |
| Auto-build on commit | Branch-scoped workflow runs on pushes and uploads an untested disposable-key ARM64 APK **only if** v0.19 compiles. Never produces a public release. |

## Technical hazards / restrictions
Reference port switches PhotoCraft to GameActivity, whereas currently released owner adapter uses NativeActivity and custom JNI, font import, keyboard tracker and AI entry points. The reference autosave implementation uses upstream RecoveryStore, which may have changed between official v0.14 and v0.19; blind copy is prohibited.

Build process uses a fresh pinned official v0.19 checkout in GitHub Actions. The existing builder's checkout-reuse rule intentionally prevents silent source replacement. A failed compatibility build is diagnostic, not permission to replace existing project or remove code.

The branch-specific GitHub Action has **contents: read** permissions and its name is deliberately outside the owner's automatic test-release publisher allowlist. An APK created by a fresh debug key is **not** compatible with the installed V2-signed stable app. Do not uninstall or overwrite the installed app based on these artifacts.

## Stop gates before any stable release
1. Correct compilation and static checks against official pinned v0.19.0.
2. Correct feature-specific code integration, host tests and ARM64 APK manifest, package and ABI checks.
3. Original **PhotoCraft V2** signing certificate match and monotonically higher Android versionCode; retain package com.artcraft.photocraft and app-private data.
4. Independent owner tablet test: font scanning/import, shortcuts, gestures, recovery, save/reopen, icon, GPU, updates, AI sidecar.
5. Owner must explicitly authorize any merge into a production branch and each GitHub Release publication. **No automatic publication.**

## Automation operation
The PhotoCraft v0.19 compatibility build automatically runs on commits to the working branch. No signing secrets are accessed. CI passes/fails are available in GitHub Actions. The review PR remains draft, and unresolved incompatibilities should be documented there rather than bypassed. When device testing or release approval is needed, stop and ask the owner.

## Additive `egui-winit 0.37` / `winit` API compatibility shim (Stage 2)

The existing Android mouse/scroll-aware `vendor/winit` is retained. Only the missing
`WindowEvent::ImeResetCompleted { request_id }` enum variant and the Android-only
`Window::reset_ime_with_request(u64)` method are added, matching the **unsupported
Android** semantics of upstream Storytold winit fork `a517b3846ee8457d84ee4975110bfda6797c44dc`:
no completion fence is fabricated and no Java IME events are consumed. This addresses
the four initial compile errors without replacing Android mouse/scroll/ESC hooks.

This is a **source compatibility attempt**, not a verified fix. The branch-only
GitHub Actions debug build and device keyboard/IME tests must still pass. Additional
v0.19 adapter/API errors may surface once dependency compilation advances. Keep
release `photocraft-v0.14.0-android.4` untouched; no public publish or production signing.
