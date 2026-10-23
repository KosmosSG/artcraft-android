# ArtCraft Android Suite — Stable + Preview release channel rollout

The owner selected **Stable + Preview Releases** for all 13 Craft apps.
Every app must allow switching to **Stable Releases Only** and persist this
choice across in-place updates. The startup update check is a separate,
optional preference and stays **OFF by default**.

**This tracker distinguishes staged source from shipped functionality.** Do not
claim an Android APK has passed device testing merely because its updater has
source checks or a GitHub workflow succeeded.

## Registered apps

| App | Source implementation status | Signed APK / physical device validation |
|---|---|---|
| PhotoCraft | Current released updater needs channel integration | Not verified for channel |
| VectorCraft | Staged: `development/vectorcraft-v016-font-feedback-20261024` | Not verified for channel |
| DesignCraft | Staged: `development/designcraft-v012-20261023` | Not verified for channel |
| FilmCraft | Pending app-specific integration | Not verified |
| PDFCraft | Pending app-specific integration | Not verified |
| WordCraft | Pending app-specific integration, preserve WordCraft PR #11 | Not verified |
| DeckCraft | Pending app-specific integration | Not verified |
| EffectCraft | Staged: `review/effectcraft-v0.13.0-android1-20261022` | Not verified for channel |
| LightCraft | Implemented: `review/lightcraft-approved-icon-20261022` | `v0.11.0-android.6` signed prerelease published; channel UI device test pending |
| SoundCraft | Pending app-specific integration | Not verified |
| CADCraft | Pending app-specific integration | Not verified |
| FigCraft | Pending app-specific integration | Not verified |
| GridCraft | Pending app-specific integration | Not verified |

## Compatibility and release acceptance criteria

1. `Help → About AppName → Updates` or the app's equivalent native UI offers
   **Stable Releases Only** and **Stable + Preview Releases**, with the latter
   initially selected for the owner's requested suite setup.
2. Persist the setting in per-app storage across in-place signed updates. Never
   conflate it with the independent startup update-check toggle.
3. Check only `KosmosSG/artcraft-android` and exact current-app tags,
   exact nonempty uploaded ARM64 APKs, increasing versionCode and permanent
   signing identity. Never accept draft releases in either channel.
4. Present any preview build as potentially untested. Never silently install
   or automatically publish; direct the user to the official GitHub release.
5. Preserve fonts, file SAF support, GPU, keyboard/UI, package IDs, version
   ordering, source provenance, independent signers and prior releases.
6. Test offline/rate limits, stable-only vs previews, drafts, same/older
   versions, unrelated app assets, preference persistence, app launch and
   device UI. Record exact signed APK SHA-256 before marking `device_verified`.

Source of truth: [feature-parity contract](../configs/feature-parity.json) and
[ArtCraft suite standard](ARTCRAFT_ANDROID_FONT_UPDATE_STANDARD.md). Issues are
currently disabled in this repository, so this tracked file avoids creating an
unmanaged task list.
