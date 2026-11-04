# WordCraft v0.14.0 Android port — guarded integration

**Status:** In development; no published or owner-approved Android v0.14.0 APK.
**Base:** exact source used for published `wordcraft-v0.9.0-android.6`, commit
`061837c6923d161bffd1709072bbce4a37aa3e0c`.
**Upstream:** `storytold/wordcraft` stable `v0.14.0`, commit
`5cd53f184aab11def13b7fced18727159b9bc96a` (2026-11-01).
**Builder:** pinned `MostafaXS1/artcraft-android` commit
`ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
**Proposed test metadata:** `com.artcraft.wordcraft`,
`0.14.0-android.1`, `100014001`, ARM64. The versionCode must be verified
above all previously published versions before production signing.

## Changes in this branch

- Add guarded `v0.14.0` handling to the existing D/C/S unsaved-dialog
  overlay. Official upstream moved the save-changes UI from `dialogs.rs`
  into `dialogs/dispatch.rs` and the dialog chrome into
  `dialogs/chrome.rs`. The original v0.9.0 overlay is retained.
- Preserve Save / Don't Save / Cancel keyboard behavior, visible hints,
  foreground focus handling and touch-blocking modal backdrop.
- Add regression checks on pinned upstream source and a negative test that
  refuses changed anchors without partially editing the source checkout.
- Add a **candidate-only** GitHub Actions ARM64 build on development commits.
  Candidate signing is disposable. The resulting APK will **not install over**
  the user's production-signed WordCraft APK, and is not publication evidence.
- Keep the original WordCraft font, SAF, menu, update feedback and icon overlays;
  all must be recompiled and checked before a v0.14.0 release.

## Android feature parity (all must be revalidated on this upstream upgrade)

| Requirement | Port strategy / release gate |
| --- | --- |
| Auto-saving documents and recovery | Preserve upstream recovery and Android persistent app paths; reopen after forced stop |
| Session save/restore | Preserve existing app settings and reopened document state; relaunch test |
| Build on commit | This branch's candidate workflow triggers on commits; no automatic publication |
| Two-finger scrolling | Inspect Android touch/egui gesture routing; test gestures on tablet |
| Better mobile UI scaling | Preserve Android density and ribbon adaptation; test portrait/landscape |
| GPU acceleration | Retain existing rendering backend; verify device GPU logs and fallback |
| Long-press right click | Verify Android long-press/context-menu dispatch without affecting typing |
| Adaptive app icon | Retain approved Wc resources; verify resources inside compiled APK |
| Adaptive cursor | Verify mouse/trackpad pointer and text input on tablet |
| Duplicate filename extension | Ensure `sample.pdf` copies become `sample (1).pdf`; SAF provider test |
| WordCraft D/C/S | Repeat shortcuts after multiple dialogs, ensure background canvas is blocked |
| Ctrl+W/new document keyboard behavior | Repeat while typing and after Cancel and Save |
| SAF font import + subfolders + feedback | Validate same fonts before/after restart, surface clear progress/errors |
| System fonts, 4 GiB scan proposals | Preserve system font discovery; separately review pending scan-budget PR |
| Update checker | App-specific signed APK filtering; explicit stable/preview channels and off-by-default startup option |
| Printing | Android system print integration with representative DOCX |
| Signing / upgrades | Original WordCraft certificate SHA-256 and monotonic versionCode, then owner testing |

## Strict gates before the user is asked to approve publication

1. Complete compatible source patching and pass all CI checks and ARM64 APK content validation.
2. Fix any build failures revealed by upstream v0.14.0 API changes. A green
   source-overlay test alone does **not** validate runtime compatibility.
3. Build a production-certificate-signed owner-test artifact **only with the
   existing independent WordCraft key**, never with a new or shared key.
4. Verify `com.artcraft.wordcraft`, versionName, versionCode, ARM64 libraries,
   adaptive/legacy icons, SHA-256 and original certificate digest.
5. Owner tests exact signed APK on HONOR MagicPad 4: reopening documents,
   save/recovery, D/C/S repeatedly, fonts, touch, scaling, shortcut pad,
   printing, and update status.
6. **Request explicit owner approval before any public release or tag.**
   Do not automatically merge this branch into main or publish anything.

This is a targeted upstream port, not a statement that the current stable
Android application already passes these tests.

## 2026-11-02 compatibility fix and test-only signing policy

- Root cause of upstream v0.14 native build failure: the pinned Android builder overwrites official `storytold/winit` fork (`a517b3846ee8457d84ee4975110bfda6797c44dc`) with older `winit 0.30.13` lacking `ImeResetCompleted` and `reset_ime_with_request`, and vendors `egui-winit 0.36.2` over an official `0.37` fork. The WordCraft-only ephemeral builder shim now guards both vendoring blocks, uses upstream `egui-winit 0.37`, and drops registration of an old 0.36-only JNI API. Android shell ClipboardManager fallback remains. This is a code change, not an assertion of compile/device success.
- Candidate-only ARM64 CI triggers once per push on the migration branch, not on the same PR event; older WordCraft 0.9 candidate workflow skips this v0.14 migration branch to avoid duplicate large builds. Source compatibility fixtures fail closed on anchor changes.
- Owner explicitly approves disposable/test-signing and uninstall/reinstall testing; no use of original WordCraft signing key or production signing workflow until final release approval. **Before uninstalling the installed production WordCraft app, export all app-private files, autosave/recovery data, imported fonts, documents and preferences, as uninstall may permanently delete them.** Temporary-signed APK cannot update the existing production-signed installation. No public release/tag/merge without owner approval.

### 2026-11-03: Build-script directory fix

- Build #41469703171 passed the new four compatibility regression tests but stopped before Cargo compilation with `cp: cannot create directory 'source/wordcraft/vendor/android-activity': No such file or directory`. Its older egui vendor block had implicitly created `$SRC/vendor`, but this block is skipped for v0.14. The WordCraft-only shim now creates this directory explicitly immediately before AndroidActivity vendoring; added a regression assertion so this cannot silently recur.
- This fixes a build-script failure, **not** proof of successful ARM64 compilation or device operation. Continue validating the fork, IME, clipboard and remaining features. The test signing key is disposable; original-key signing/public release require owner permission.

### 2026-11-03: v0.14 launcher API adjustments

- The candidate build [#41560966077](https://github.com/KosmosSG/artcraft-android/actions/runs/41560966077) passed the guarded source tests and compiled past the previous winit and missing-directory failures, but native build exited with two Rust API errors: `craft_ui::printing::Printer` now requires `label: String`, and WordCraft `WordApp::raw_input_hook` now requires `(ctx, raw)` rather than only `raw`.
- The WordCraft-v0.14-only builder compatibility shim adds an empty `label` (shared print UI falls back to existing `name`, so it still displays Android print system) and changes the generated WordCraft raw-input hook to pass `ctx`. It retains the existing older input hook for all other apps. Guarded regression fixture tests both changes and ensures missing anchors abort.
- **Build success, actual print submission, D/C/S behavior, clipboard, IME and tablet acceptance remain unverified until a successful candidate and owner testing.** Never use original certificate for this test.

## 2026-11-03: HONOR MagicPad test feedback for android.2 preview

- Device tested android.1: user reports launcher icon missing in top-left UI ribbon, D/C/S not working, and shared folder scan too small. **None of the three new fixes have passed device validation yet.**
- Android.2 uses the exact approved launcher artwork as an embedded 40x40 RGBA texture and renders an ArtCraft popup button at the start (left side) of the tab strip, rather than text-only menu inside the right-to-left buttons group.
- Android.2 adds WordCraft-only raw-key D/C/S intercept before editor processing, in addition to existing Java physical-key dispatch and v0.14 dialog handler. Preserves Save/Don't Save/Cancel button actions; clears stale JNI action on modal close.
- Recursive shared SAF font scan: 5,000 recognized fonts, aggregate 4 GiB file data, up to 20,000 folders, with a 256 MiB per-file safety limit, streamed 64 KiB at a time and asynchronously staged. Font load processes up to 8 files per frame. Actual free app-private storage must be adequate. No blanket filesystem permission or signing-key changes.
- Scope: draft PR117 only, temporary-signed candidate `0.14.0-android.2`. Do not merge, publish or use original certificate until explicit user approval after testing.

### 2026-11-04: egui v0.37 icon-button compile fix

- CI [#41605782234](https://github.com/KosmosSG/artcraft-android/actions/runs/41605782234) passed static D/C/S, icon and 5,000-font / 4 GiB checks, but Rust failed with `E0433` because egui v0.37 removed the old `egui::ImageButton` widget. The **pinned Storytold egui 0.37 source** provides `egui::Button::image` in `crates/egui/src/widgets/button.rs`. Use that supported widget with the existing approved icon texture and popup; update regression to reject the removed `ImageButton` name. No other feature or signing changes. An ARM64 build and MagicPad test are still required.

## 2026-11-04 WordCraft preview android.3 — Device feedback

- Device screenshot: approved glossy Wc app icon appears at top-left, but an unwanted rounded-square outline is painted around the egui icon button. Switch `egui::Button::image(...)` to `.frame(false)`, preserving the same approved artwork, menu trigger, hover, and launcher PNG.
- User also reports two-finger physical trackpad scrolling does **not** move the document canvas as touchscreen swipe does. Pinned Storytold winit Android backend handles finger touch input but ignores ACTION_SCROLL from Android pointer devices. Add a WordCraft-only `GameActivity.dispatchGenericMotionEvent` bridge for ACTION_SCROLL with SOURCE_MOUSE or SOURCE_TOUCHPAD, both H/V scroll axes, android-configured pixel scroll factors, thread-safe coalescing, Java→Rust JNI polling. Emit egui `PointerMoved` (hover target) + precise `MouseWheel{Point,Trackpad,Move}` after scaling by live egui pixels-per-point, so existing upstream 1:1 `scroll.rs` canvas code handles natural panning without duplicating touch events, synthetic touch drags or intercepting Android navigation gestures. Android framework gesture mapping varies; **hardware test required** to confirm trackpad scroll events are delivered on MagicOS.
- New source-level regression guards cover icon frame and two-axis scrolling bridge. No blanket storage permissions or upstream, stable-signing, shared-suite behavior changes; version `0.14.0-android.3` temp-signed candidate, original public release remains protected.

## 2026-11-04 WordCraft android.4 — physical D/C/S and Save As

- Device screenshot of v0.14.0-android.3 confirms D/C/S touch buttons work, physical D/C/S do not. Previous raw input handler listened only for Key events and silently discarded Text events; MagicOS/Gboard can deliver committed letters as Text or Ime Commit instead. Updated WordCraft-only raw handler accepts unmodified single-character D/C/S from egui Key, Text or Ime Commit **only while the unsaved-changes modal is active**, queues only one action and keeps the touch buttons unchanged. Added WC_DCS_DIAG source log. Actual physical keyboard behavior remains subject to device testing.
- Ctrl+Shift+S when no modal is open is now queued from either the raw input path or Java Activity dispatch and triggers the existing WordApp.save_as_dialog / SAF chooser on the Rust UI thread. No direct file write, no change to Ctrl+S, dialog D/C/S modifiers or existing menu Save As.
- Keep all other approved features (frameless Wc icon, trackpad two-finger scroll, fonts 5000 / 4GiB, D/C/S hints) unchanged. Next preview v0.14.0-android.4, code 100014004; disposable test certificate only, original production signing/publication require explicit owner approval.


## 2026-11-04 WordCraft Android.5 — MagicPad hardware-keyboard, touch and clipboard audit

- Device-tested android.4: physical D/C/S still fails; touch buttons work. Hidden Android EditText can receive physical key events through InputConnection.sendKeyEvent, onKeyDown/up, and text commits before Activity dispatch. The WordCraft-only builder injects one wcHandleHardwareShortcut/wcHandleImeChoice method across these routes. D/C/S is intercepted only while the unsaved-changes modal is active; egui raw fallback retained. Native device test still required.
- Esc maps to **Cancel (C)** while the Save Changes dialog is open; it must never discard changes. Native egui and Java Activity/IME hardware paths cover it. A suite-wide compatibility policy is documented separately, but no other app code is changed.
- Ctrl+Q calls upstream WordApp::quit() via the Rust UI thread; only closes the window after the existing unsaved-document check permits. Dirty work must open D/S/C.
- Touchscreen two-finger pan tracks exactly two contacts and stable inter-finger separation. It preserves native touch/pinch events, coalesces centroid movement and sends precise canvas wheel events. On-device smoothness and gesture interaction must be verified.
- Clipboard A->B: official upstream egui-winit 0.37 uses an Android app-internal fallback. WordCraft's Android shell reads Ctrl+V from the system clipboard but previously never called the existing android_clipboard_set. After WordCraft emits egui::OutputCommand::CopyText, mirror text into Android ClipboardManager. Verify selected text A copied to the system clipboard, then pasted over location B, not a stale clipboard value. This does not change selection logic or Ctrl+V handling.
- Scope: WordCraft PR117 only, preview 0.14.0-android.5, per-run disposable signing; no production key, merge, tag or release without approval. Compile checks are not hardware validation.
