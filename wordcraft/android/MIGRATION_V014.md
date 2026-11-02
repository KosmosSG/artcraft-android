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
