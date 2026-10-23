# ArtCraft Android Suite — mandatory Android app conventions

Scope: every ArtCraft Android app maintained in this repository, including future Craft apps and Android-specific forks. Keep this guidance with the repository; it applies to contributors and automated development workflows.

## PhotoCraft-style in-app update controls (REQUIRED for future builds)

- Preserve the native app's existing Help menu. Add **About AppName**, immediately followed by **Check for Updates** and **Startup Update Settings** in the same Help menu. About is normally a dialog action, not a submenu. Use the closest equivalent if the application's menu architecture genuinely differs.
- Manual **Check for Updates** is always available. **Check for updates at startup** is an opt-in switch, persisted across application upgrades and **OFF by default**. Checks use bounded asynchronous I/O; network outages, timeouts and GitHub rate limits must never block app launch or editing.
- Check the official `KosmosSG/artcraft-android` GitHub Releases feed. Match **only the current app's** exact tags (`appname-vX.Y.Z-android.N`) and exact nonempty, uploaded signed ARM64 APK assets. Exclude drafts; exclude prereleases by default unless an explicitly authorized preview channel is implemented. Reject unrelated apps, generic `arm64` substring matches, old and lower versions, malformed version tags, and ambiguous assets.
- Compare the installed Android `versionName` **and** monotonically increasing `versionCode`. Match `applicationId` and the same independent permanent signing certificate for in-place updates; record/verify SHA-256 and APK identity before distributing updates. Never replace or regenerate an existing app's permanent signing key to work around a failed build or release.
- Default to presenting version details and opening the matching official GitHub Release in the browser with user approval. Never silently install an APK, erase app data, change package identity, or publish a release without authorization.
- Use the standard Android naming convention: **AppName vX.Y.Z-android.N** (title), `appname-vX.Y.Z-android.N` (tag), `AppName-vX.Y.Z-android.N-arm64-v8a.apk` (canonical APK). Retain an identical-bytes legacy alias when an older installed updater genuinely requires it.
- Implement app-native behavior compatible with its architecture. PhotoCraft is the design/behavior reference; copying its implementation blindly is not sufficient.

## Required evidence for each app

1. Read [docs/ARTCRAFT_ANDROID_FONT_UPDATE_STANDARD.md](docs/ARTCRAFT_ANDROID_FONT_UPDATE_STANDARD.md), [configs/feature-parity.json](configs/feature-parity.json), and [tools/suite_feature_parity.py](tools/suite_feature_parity.py) before starting a new app or release workflow.
2. Register every new Craft app in the version/release-gate config **and** the suite feature-parity contract; update the 13-app validation schema/tests deliberately. Existing apps must preserve their feature requirements.
3. Add app-scoped tests for Help-menu placement, persistent OFF-by-default startup preference, exact release/asset filtering, network failure handling, monotonic versioning, and original signing identity. Run these alongside normal Android compile and APK signature/ABI verification.
4. Distinguish source verified, artifact verified, and **physically device verified**. Verify the exact signed APK on the HONOR MagicPad 4 when available; never mark a feature `device_verified` without evidence tied to its exact APK SHA-256.
5. Follow the independent signing and publication gates for each app. The suite's central audit validates the contract but does **not**, by itself, prove runtime behavior or authorize production publication. Separately authorized untested preview releases must be labeled clearly.

These are **future development/release requirements**, not assertions that every existing Android APK currently implements the updater.
