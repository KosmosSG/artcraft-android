# EffectCraft official v0.20.0 → Android compatibility trial (2 November 2026)

**Draft only — NOT approved for publishing or production signing.**

This is a stacked follow-up to EffectCraft draft PR #82. It starts at PR #82's head, **not** the outdated shared `main` tree, so it keeps the existing EffectCraft v0.16.0-android.8 source modifications. The existing public v0.16.0-android.5 release and previous signed APK are untouched.

## Source versions

| Source | Identity |
| --- | --- |
| Latest verified stable official release | `storytold/effectcraft v0.20.0` |
| Immutable upstream tag target | `720c67117ea232ef01631a368bb617012f4c63d6` |
| Existing Android feature baseline | PR #82 / `feature/effectcraft-unsaved-dcs-20261028` |
| v0.16 Android integration scripts | `tools/effectcraft/` (preserved) |
| Source tree structure change | v0.20 moves top-menu implementation from `menus.rs` to `menus/bar.rs` |

The reference `MostafaXS1/artcraft-android` is guidance only; do **not** substitute its builder over the customized `KosmosSG` implementation.

## Implemented in this trial

- Extend the EffectCraft-specific update/font-menu injection to choose the v0.20 modular menu implementation while retaining the v0.16 legacy path.
- Add automated regression tests for both layouts and mismatched/duplicate hooks.
- Automate an isolated upstream v0.20.0 ARM64 compilation attempt with a strict SHA pin.
- Use only a **temporary signer** and a separately installable `com.artcraft.effectcraft.v020test` trial package.
- Give the trial a test-only `0.20.0-android.1` / `16810001` identity. **This does not reserve or authorize a production Android version.**
- Upload candidate artifacts only to the workflow's private Actions artifacts, if and only if the complete compile and APK checks pass.
- Build/test in `feature/effectcraft-v020-android-port-20261102` on GitHub pushes; no auto-merge, no production keystores, no GitHub Release.

## Features that must survive the upgrade

No loss of Android SAF open/save, autosave and crash recovery, saved session recovery, settings, stylus/touch and two-finger scroll, mouse long press/right-click, keyboard Escape/D-C-S, native IME, font discovery (including recursive 4 GiB scan and shared SAF folder), native update popup and preferences, approved Ec launcher/adaptive icon, honest GPU diagnostics, or access to host-wired media/import/export/expressions.

The v0.20 trial runs the existing conditional patches against the new source and **fails closed on source drift**. A passing structural test is *not* a passing build. A passing build is *not* proof that the Android device behavior listed above works. Mark each feature verified only after device testing on the exact test APK.

## Known compatibility risks / next steps

1. v0.20 also split the UI application implementation into `app.rs` and submodules. Confirm the generated Android launcher still uses correct methods and lifecycle.
2. Review v0.20 fonts, text-edit / unsaved dialog commands and Android keyboard event plumbing. Existing v0.16 D/C/S and font patches must compile unchanged or receive purpose-specific updates, never be silently dropped.
3. Review dependencies/codecs, JNI runtime, SAF permissions and background I/O; ensure GPU acceleration is only claimed when actually active.
4. If source checks or compilation fail, inspect the workflow failure and patch the isolated v0.20 branch, preserving v0.16 compatibility. Repeat until all CI checks pass.
5. Only then deliver the test APK for HONOR MagicPad 4 verification, including reopening prior projects, crash/session restore, nested 4 GiB font scan and input behavior.
6. For a **production** candidate, confirm the separate original EffectCraft signing certificate SHA-256 `10c93a0a55b9d66b6c64ac87372d5f3118c74a11c99fecb6e9f3951d2cbe8577`; select a code higher than all installed/published codes; verify exact APK contents and checksum. No release without explicit owner approval.

## Publication gate

**Never auto-publish** this candidate. Stop and notify the owner before any production signing, merge into a release branch, release tagging, or publishing. Any unavailable signing secret, incompatible compilation or missing physical-device evidence is a hard stop.
