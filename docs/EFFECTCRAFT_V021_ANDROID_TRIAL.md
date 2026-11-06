# EffectCraft v0.21.0 ARM64 isolated Android trial — 2026-11-04

**Development-only, no production signing or GitHub Release. EffectCraft only.**

## Baselines and source provenance

- Published/approved Android baseline: `effectcraft-v0.16.0-android.8` (tag commit `9d5197b30a53071841a7592975e16757c41f22d9`). Preserve its release, signing key, source and user data.
- Existing successfully compiled v0.20.0 temporary APK candidate: Actions #41598646331, draft PR #116. Preserve as a fallback; a compile success is not device verification.
- This trial branches from PR #116's head, `13b2da6b5b8ab8500b9fbd1b7d2cbb1c9d9bf3c8`. It reuses existing EffectCraft Android font/DCS/updater/UI wiring rather than replacing the customized fork.
- Official stable upstream `storytold/effectcraft@v0.21.0`, immutable commit `7870b5916ae0749d497d880989683bf2946d6c8b`. This is newer than the v0.20.0 trial.
- Both v0.20 and v0.21 pin the identical `storytold/winit@a517b3846ee8457d84ee4975110bfda6797c44dc` and `storytold/egui@6d518fc799681571963842f95b55a6b68431b15a` fork revisions. Reuse the previously tested input/IME compatibility staging only if its structural guards pass.
- Verified upstream v0.21 still has the guarded modular menu anchor in `crates/ui-egui/src/menus/bar.rs`; source patches fail closed on unexpected drift.

## Candidate identity and safety

- Test-only `versionName=0.21.0-android.1`, `versionCode=16820001`, architecture `arm64-v8a`.
- Separate test package `com.artcraft.effectcraft.v021test`, different from installed stable app `com.artcraft.effectcraft`.
- Original Ec art/branding assets preserved; only metadata version fields are updated in an isolated runner checkout.
- Disposable keystore is generated in the temporary job and deleted after the build. No production signing repository, GitHub secrets, production signing workflow, release tag, or publication is accessed.
- No automatic merging into main or other apps. GitHub Actions artifact only, three-day retention; user device-test approval required. This branch has no automatic production release path.

## Regression gates

Ensure Android SAF file open/save, native D/C/S and Esc, physical keyboard, native IME, keyboard navigation, 4 GiB/5,000 recursive custom font scanning and SAF folder handling, in-app update popups and settings, touch/trackpad scrolling, GPU diagnostics and fallback, app icon, media import/export, autosave/session restore, and long-press semantics remain operational. These require actual device verification; a green APK build is not proof of all runtime behavior.

## Known boundaries

The reference builder's advanced autosave mirror/session restoration, adaptive cursor, long-press right click, and 2-finger gesture parity were not all proven in PR #116's source audit. Do not claim they were tested or implemented if not verified. If the v0.21 staging or build fails, investigate in this branch only and preserve the v0.20 fallback. Do not downgrade or remove an approved Android feature to make a build green.

**STOP after temporary-signed APK delivery. Await device testing, separate approval to permanently sign, and explicit authorization to publish.**
