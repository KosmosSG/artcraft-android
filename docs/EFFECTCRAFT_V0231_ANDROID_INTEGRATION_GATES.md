# EffectCraft v0.23.1 Android integration — protected-gate audit (2026-11-10)

## Verified immutable anchors
- Official upstream: `storytold/effectcraft` tag `v0.23.1` → `f5e5c8a4d8e0d5aa7e5493b527c0773969a4364a`.
- Published Android baseline: `effectcraft-v0.21.0-android.15` → `d27a301f22e71e58ac1e17a0c9fe54728ff99ec9`.
- Integration branch: `integration/effectcraft-upstream-20261110` starts directly from that baseline, contains a *metadata pin only* at audit time. It is **not** yet an upstream source port.
- Existing `tools/effectcraft/upstream-lock.json` still documents an older v0.16.0 trial; `tools/effectcraft/v021_compat.py` and old workflows pin v0.21.0. Do not treat those as a v0.23.1 build recipe.

## Required before enabling CI
1. Audit actual v0.23.1 API differences for editor session, host-backed import/export, keyboard and dialogs, renderer, text/fonts, menu and native winit. Reapply only compatible changes in the *EffectCraft-only staged source*, not the shared baseline.
2. Port approved Android.15 adaptations without dropping compact Ec menu, keyboard tools/ESC, repeat D/C/S, Ctrl+Q, Appearance, SAF font import and recursive 5,000 file / 4 GiB scan, updater, cursor and GPU/gestures.
3. Ensure 2-finger touchscreen/trackpad pan never creates a selection rectangle, pinch works, no rejected Export Gesture Log/Fonts/Updates menu duplicates. Source-level tests must check those regressions and fail closed on upstream drift.
4. Stage exact `v0.23.1` SHA, separate `com.artcraft.effectcraft.v023test` package, temporary signing key, arm64-v8a only; preserve production package, data, file associations, icon and original signing material. Avoid production keystore/secrets.
5. Run fast static/unit checks before **one** batched ARM64 compile; check APK badge/version/ABI, signature, zip alignment, hash, size and installability. Upload artifact only; no Release, merge or production signing.
6. Owner tests on HONOR MagicPad 4 (165 Hz): 10 cold starts, 10 Ctrl+Q relaunches, shortcuts/IME, repeated Ctrl+W D/C/S, font import/refresh, gestures without canvas selection, menu scrolling, zoom, updater, project save/reopen and GPU fallback.

## Current gates
- Official tag verified: **PASS**
- Protected baseline and branch ancestry verified: **PASS**
- v0.23.1 source selectively integrated: **NOT DONE**
- Regression tests: **NOT RUN**
- ARM64 test build/APK: **NOT AVAILABLE**
- Tablet acceptance: **PENDING**
- Merge/permanent sign/publish: **PROHIBITED** until explicit approval

Do not trigger a legacy v0.21 workflow and mislabel its output as v0.23.1.
