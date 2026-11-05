# VectorCraft Android.10 stability investigation

Work in progress. No APK or device acceptance claimed.

## Immutable evidence

- Protected published release: `vectorcraft-v0.14.0-android.13`; tag commit `9d5197b30a53071841a7592975e16757c41f22d9`.
- Published APK GitHub digest: `3c3454668ecc8310a725683fd8818e08e6ff4d8dbbd0ad9c014a30e61afac3d0`.
- Public .13 compile workflow pins owner source `17990043fc15f038a8046b0857abc09281fe67e0`, builder `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`, upstream `ad0566943ab9741e6356bbc9b53c3cc09895068d`. This differs from the release tag. Exact published-APK payload equivalence has NOT been established; this is a provenance gap, not permission to retag the stable release.
- Candidate .9 source `e451687a9661cec0722db39ef3f2913659eee349`; successful build https://github.com/KosmosSG/artcraft-android/actions/runs/41990353065 . Device failures reported by owner despite compilation passing.
- New work starts from that exact candidate, preserving its approved features; it is NOT claimed to reconstruct the exact stable APK source.
- Upstream v0.21.0 `11862f61198c8f62c0b22b6c9a331cc5950ac98d`; builder `fbb4f66fcc868afdd8303d5227aa81db6a21d7fa`.

## Confirmed source defects / corrections under test

| Area | Evidence | Correction | Verification still required |
|---|---|---|---|
| Modifier state | Builder winit discards Android meta state; adapter overwrites event modifiers using only held-key history | Forward per-key Android snapshots before KeyboardInput, remove competing adapter reconstruction | Physical modifiers, clipboard and IME on device |
| Uneven tool shortcuts | V/T/P bypass upstream customizable keymap; other letters do not | One upstream tool dispatcher; retain guarded missing-Text fallback | All tools and custom bindings |
| Save Changes | Late paint-time mnemonic handler independent of once-per-frame shortcut routing | Modal-only handler in existing shortcut dispatcher, original commands for save/cancel/discard | Repeated physical keyboard sequences; exact point of historical event loss remains unproven |
| Quit/relaunch | winit ignores MainEvent::Destroy and process-wide loop-created guard remains set | Normal destroy exit and Android-only guard reset when old loop drops | Repeated same-process Activity recreation, cold relaunch, recovery; historical data-clear incident not reproduced |
| Startup | PixelCopy brightness thresholds reject valid dark frames; system pre-draw waits for native readiness | Presented-buffer success after editor traversal, no brightness test or blocked system pre-draw | Cold/warm device timing and black-frame observation |
| Trackpad | Adapter low-pass clamps deltas; additional menu multiplier/timer layered on egui | Remove both extra smoothing layers; preserve precision delta and phase, retain Vulkan renderer | Device frame pacing/GPU measurement and all gesture regressions |

The previous .7/.8 failed runs 41856921081 and 41858508545 failed compilation on missing MouseWheel `phase` fields and an event borrow/move error. Those logs do not explain the later device failures. Existing 71 Python tests passed (one JVM skip) before edits, but predominantly assert source strings. New tests exercise generated Rust helper behavior and real upstream document/save/quit commands. Earlier local edits and an unfinished test run were lost in a workspace reset; only the recorded four input-test passes are established from that run. Tests must run again on persisted source.

## Preservation and scope

Only VectorCraft test build scripts are changed. Font scanner, updater, adaptive cursor, owner icon, SAF bridge and stable package remain inherited. The new overlay replaces obsolete input/scroll patches in the test workflow; old workflows remain historical rollback references, not the source of the new corrections. Production credentials are neither used nor read. Stable releases/tags are unchanged. The target is `com.artcraft.vectorcraft.test`, `0.21.0-android.10`, ARM64, disposable key, Actions artifact only.

## Device checks (all DEVICE TEST REQUIRED)

1. Cold/warm startup; capture VC_STARTUP timings and any black frames.
2. V/T/P and other tool shortcuts, custom bindings, Ctrl/Shift/Alt, copy/cut/paste.
3. Type text, ESC, switch tool; repeat after picker return and touch/trackpad switching.
4. Ctrl+W then D/C/S, 20 repetitions; new/existing files and multiple modified documents.
5. Cancel a Save As picker and simulate provider failure: document must remain open and dirty.
6. Ctrl+Q clean/dirty, Cancel, Save, Don't Save; reopen repeatedly without clearing data.
7. Long menu trackpad scrolling; mouse wheel, touchscreen, canvas pan/pinch; cursor hover styles.
8. Font import/folder/refresh, cached fonts, update checker/settings, correct icon/menu, autosave/recovery.

Keyboard Diagnostics under Vc is opt-in, holds only a latest numeric key snapshot, redacts identity during typing/composition, and does not record text, paths, passwords or command parameters. Frame interval statistics include idle periods and are NOT GPU execution measurements.

## Latest checkpoint

- Restored input-helper suite: four behavioral tests passed.
- Existing Python suite: 71 tests run successfully, one JVM-dependent test skipped.
- Font scanner/updater helper and adaptive-cursor source byte comparisons against Android.9 passed.
- Final-vendor backend anchor validation and duplicate-application rejection passed.
- Android.10 workflow YAML, read-only token, no production-secret references, and removal of obsolete modal/scroll patch invocations checked.
- Save/quit tests are still compiling in a fresh /tmp target directory after two prior attempts failed on corrupted compiler artifacts; no passing result claimed.
- No Android.10 APK built or signed. No workflow triggered.
- Local changes have NOT been uploaded. Automatic approval review rejected pushes to the authorized repository because it did not accept the attached-brief authorization as verified end-user approval. Await explicit user confirmation before retrying.
