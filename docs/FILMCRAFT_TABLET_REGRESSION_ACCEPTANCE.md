# FilmCraft tablet regression acceptance — 25 October 2026

Owner feedback: GPU not detected; Font Import and Check Updates unavailable. Treat these as unresolved failures, not successful device acceptance. Exact tested APK SHA/version is not yet correlated with the integrated .2 candidate.

## Current evidence

PR55 integrates the PR7 runtime overlay and PR49 approved launcher/native header branding. Candidate https://github.com/KosmosSG/artcraft-android/actions/runs/40116379609 passed at aadff0ac79f42902aca711633069dbd291d4612e. That build result does not disprove the owner's observed missing controls. Do not release or sign using the older PR27 .1 allowlist.

## Required regression scenarios before release

- From a fresh launch and after loading a video project, navigate the native menus and locate Import Font and Check Updates without relying on a hidden overlay button. Verify both actions reach the Android bridge. Missing native placement is a UI integration defect even if bridge source tests pass.
- Import a valid TTF and OTF via SAF, cancel a picker, reject malformed font data, reopen the app and confirm persistence. Confirm the imported family renders in actual FilmCraft titles and survives project save/reopen/export, not merely the egui UI font list.
- Select a shared font folder, refresh after adding a font, revoke access and retry. Report an actionable result and preserve already imported fonts on failure.
- Manual update check must show checking, no-release/up-to-date/new-version, offline and HTTP failure outcomes. Startup check must remain optional and persist. Reject other-app APKs, incomplete assets and downgrades.
- GPU diagnostics must report the renderer actually selected, adapter/backend when available and an explicit unsupported/unavailable reason otherwise. CPU fallback must be truthful. Never fill an unknown field with guessed Adreno/device data.
- Preserve video/audio playback, timeline input, SAF media access, project round trip and export. GPU detection changes must not bypass media-engine tests.

## Evidence to retain

For each scenario attach exact APK SHA256, package/versionCode, certificate fingerprint, source/builder/overlay commits and test outcome. Keep automated compile/package checks separate from HONOR MagicPad 4 device results. Maintain existing permanent signing identity and monotonic reserved production codes; no key setup or publication is implied by this record.
