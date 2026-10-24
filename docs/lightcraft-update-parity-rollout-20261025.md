# ArtCraft Android Suite — LightCraft-style Update Experience

**Approved reference:** user's 25 October 2026 screenshot of LightCraft v0.11.0-android.6, About LightCraft > Updates. Preserve each upstream app's existing style and architecture; do not copy code without a compatibility audit. This is a rollout specification, **not proof of rollout or device verification**.

## User experience (every app when compatible)
- Help > About App > Updates, or Help > Check for Updates opening the same content.
- Clear **Installed Version** and latest available **verified** version.
- Functional, repeatable **Check for Updates** button. Immediately show a spinner/checking message; end with distinct up-to-date, update-available, no compatible release, timed-out and offline/network error states. Never leave a silent nonresponsive button.
- Radio selection: **Stable Releases Only** (new install default) or **Stable + Preview Releases**; save per-app user choice and respect an existing choice after upgrade. No drafts.
- **Check for updates at startup** persisted opt-in (default OFF on new installs). Startup checks are background and must never interrupt editing or open unsolicited dialogs.
- **Open Official GitHub Release** only when a *genuinely newer* app-specific release is available and URL/tag/APK identity pass verification. The link must never install silently.
- The updates panel is a scrollable dialog; do not permanently reserve canvas/dock space for background status.
- Installed candidate/test package that has v0.14.0 must **not** be told v0.12.0 is newer merely because test-signing versionCodes differ. Production update eligibility checks **both** monotonic versionName and versionCode and identical signing identity/package.

## Font import companion checks
- TTF/OTF using Android SAF, persist each imported font without filename collisions across app restarts, reject corrupted fonts and report the actual detected **family names** from each app's live font engine.
- Refresh the font family dropdown on success, preserve font files across restarts, add user-visible diagnostics to distinguish a stored file from a registered font; scan shared SAF tree with permission limits.
- A successful SAF copy alone is *not* sufficient for acceptance. Test actual use of an imported font in a text layer/object and export output.

## Rollout matrix

| App | LightCraft-style updater | Acceptance state |
| --- | --- | --- |
| LightCraft | Reference UI from owner screenshot | Existing v0.11.0-android.6 UI pictured; unchanged |
| PhotoCraft | In implementation on v0.14.0 Android branch (PR #28) | New APK CI + font/dropdown testing pending |
| VectorCraft | In implementation on v0.16.0 Android branch (PR #39) | New APK CI + dialog tablet testing pending |
| DesignCraft | Compatibility review required | Not verified |
| EffectCraft | Compatibility review required | Not verified |
| FilmCraft | Compatibility review required | Not verified |
| PDFCraft | Compatibility review required | Not verified |
| WordCraft | Compatibility review required | Not verified |
| DeckCraft | Compatibility review required | Not verified |
| GridCraft | Compatibility review required | Not verified |
| SoundCraft | Compatibility review required | Not verified |
| CADCraft | Compatibility review required | Not verified |
| FigCraft | Compatibility review required | Not verified |

For each not-verified app, locate the current upstream About/Help code, Java/native bridge, and existing updater before modifying. Add a per-app PR, tests that prohibit regressions, disposable ARM64 Test APK, device signoff, then only an independent permanently signed production APK after matching the prior public APK's signer/versionCode. Never claim compatibility without checking the actual implementation.

## Build/release constraints
- Official upstream source/tag remains pinned; no automated synchronization.
- GitHub Releases only; no Play Store or auto-publishing.
- Original app icons (launcher and top-left UI), package IDs, permanent keys, fonts, document import/export and feature enhancements remain unchanged by policy.
- No old test APK should be published as a production update.
- The shared contract is in `configs/feature-parity.json`, key `update_ui_contract`. All app statuses remain **not_verified** until artifact/device proof.

## Test cases
1. New install: startup OFF and stable channel default. Repeat manual check; visible checking -> result/error.
2. Offline and GitHub API limits: error visible, app remains responsive. Timeout closes spinner.
3. Public release for a *different* app, wrong asset, draft and preview under Stable Only: ignored.
4. Older release whose Android versionCode happens to be greater than the test build: never shown as update.
5. Signed production APK: original package and original signing cert, higher versionCode, in-place update without data loss.
6. Font: import a known TTF/OTF, confirm family in live catalog, select it in editor, reopen app, export.
7. Tablet dialog: visible, scrollable, close/reopen works; startup check never opens modal.

References: [PhotoCraft test development](https://github.com/KosmosSG/artcraft-android/pull/28), [VectorCraft test development](https://github.com/KosmosSG/artcraft-android/pull/39), [manual release gates](https://github.com/KosmosSG/artcraft-android/pull/52).
