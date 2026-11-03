# DeckCraft Android: protected upstream v0.15.0 staging

**Status:** Phase 2 first run `41675943962` failed only at APK version verification after passing build/tests. Corrected disposable branding metadata; second test run `41682410373` underway. **Not yet device-tested, permanently signed, or published.**
**Baseline:** published `deckcraft-v0.14.1-android.17`, source `54fbdd4088d0e835c7642fafe039a72c3993be72`.
**Rollback:** the published Android.17 release and original release certificate must remain intact.
**Upstream target:** official `storytold/deckcraft` v0.15.0, pinned at `3e178d8f5a59c787a6a53a7ed0f052b3e4a1489f`.
**Staging branch:** `integration/deckcraft-upstream-v0150-20261104`.
**Test identifier (not a release):** `0.15.0-android.18-test`, versionCode `100000022`.

## Non-negotiable feature preservation gates

Retain all approved Android.17 behavior and patches; do not replace these with vanilla upstream files:

- User-approved borderless glossy red Dk launcher icon and matching top-left interactive Dk menu, left aligned. Do not duplicate Help items in it.
- D/C/S dirty-document modal including keyboard Ctrl+W behavior, Android save acknowledgements, safe cancellation, modal focus, and Escape/back handling.
- Canvas text selection, Backspace/Delete behavior, arrows and Shift+arrows, clipboard shortcuts, and physical keyboard/IME handling.
- Smooth one-finger/two-finger touch and trackpad interaction, canvas pan, wheel zoom, and input-gesture isolation.
- Dark theme, tablet tools, autosave/session recovery, and on-device UI scaling.
- Imported TTF/OTF fonts, persistent SAF-selected folders, recursive scan up to 5,000 accepted font files, 4 GiB cumulative scan/cache budget, and font refresh.
- Vulkan/WGPU UI composition, truthful GPU adapter diagnostics, slide texture cache reuse, and original CPU raster fallback.
- Per-app verified GitHub update checker, opt-in startup checks, SHA256/package/ABI/version/certificate checks, and Android installer user confirmation.

## Integration protocol

1. Only change the isolated staging branch. Never overwrite the source tree/tag of Android.17.
2. Use pinned upstream v0.15.0; do not blindly merge upstream into Android patch scripts. Existing patches must fail closed on anchor drift.
3. Review changed upstream files and ensure Android patch anchors are compatible. As of this staging change, 16 representative upstream source anchors were checked and found present; this is **not** a full patch execution, compile, or behavior test.
4. The `.github/workflows/deckcraft-v013-integration.yml` staging branch copy retains all Android patch steps and source probes, but now has **manual dispatch only** and a required `temporary_arm64_build_approved` input (default false). No push-triggered test builds.
5. When the owner separately authorizes the build, run source patch checks and existing `android_` regression tests first, then one ARM64 candidate build. Do not rebuild after each small edit; batch issues. Use only disposable packaging keys for tests and remove/strip the disposable signature as the workflow prescribes.
6. For physical testing, use a disposable test signature and back up documents; a test-key APK cannot update a production-key install in place.
7. Stop on any new regression, unexpected build modifications, or signing-identity mismatch. Preserve the rollback APK.
8. **Permanent production signing requires separate explicit owner approval** after device test confirmation. **Publishing requires another explicit approval**. No automatic publishing; no release secrets in the development workflow.

## Upstream v0.15.0 compatibility attention

- `crates/fonts/src/fontdb.rs`: monospace fallback changed; keep SAF and 4 GiB font scan integration.
- `crates/ui-egui/src/lib.rs`: presenter module and command help changed; keep Android app menu and IME guards.
- `crates/ui-egui/src/services.rs`: new presenter service; keep Android save acknowledgement callbacks.
- `crates/ui-egui/src/backstage.rs`: Account becomes About; keep existing appearance options and normal Help menu.
- `crates/ui-egui/src/show/*`: browser presenter improvements; ensure Android slideshow and input behavior do not regress.
- Other upstream improvements include PPTX tag limits, text inset layout, multi-shape resizing, alpha operations, and rendering effects. Regression testing remains required.

## Current check results

- [x] Source branch created from exactly the protected Android.17 commit.
- [x] Official upstream v0.15.0 release and exact source SHA verified.
- [x] Representative upstream Android patch anchors checked: 16 present / 0 missing.
- [x] Test workflow staged with manual approval gate, no production secrets, no publication commands.
- [x] Phase 1 verified zero Actions runs; Phase 2 triggered **one** approved run: `41675943962`.
- [x] One-time Phase 2 push trigger removed after kickoff; new builds require explicit `workflow_dispatch` approval input.
- [x] Full patch application against v0.15.0 — passed during run `41675943962` (step 11).
- [x] Cargo and Android ARM64 compiler tests passed on run `41675943962`.
- [ ] Postbuild APK verification: run `41675943962` failed because approved-branding overrode candidate version metadata back to Android.17; no artifact uploaded.
- [x] Repaired only disposable build workspace metadata (`builder/tools/approved-branding/assets/manifest.json` and `builder/lib/android_project.py`) to candidate `0.15.0-android.18-test` / code `100000022`. Published Android.17 manifest and Dk icon assets untouched.
- [ ] Repaired one-time testing rebuild `41682410373` running; candidate APK integrity, temporary signing and artifact availability pending.
- [x] One-time rebuild push trigger removed after accepted queue event; workflow is again manual/approval-gated.
- [ ] On-device testing — pending owner's test confirmation.
- [ ] Permanent signing — prohibited until explicit approval.
- [ ] Public release — prohibited until explicit approval.

Do not describe this staging branch as regression-tested or ready for production until the pending gates have actually passed.
