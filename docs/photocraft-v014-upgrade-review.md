# PhotoCraft Android 0.14.0-android.1 — safe upstream migration

## Source and baseline

- Official upstream: `storytold/photocraft` tag `v0.14.0`, commit `ff4738810134d7f7e68b49f2e4f231b686282ff3`.
- Android baseline: publicly released `PhotoCraft v0.12.0-android.1`, source `dde9b35c804ac1ef12509735f94de11d7cb4a8f5`.
- Main ArtCraft suite branch is **not** the released PhotoCraft adapter baseline. This upgrade branch starts at the released PhotoCraft commit instead of replacing it with older main-branch code.
- Official Rust requirement: 1.95, edition 2024. Existing package: `com.artcraft.photocraft`, target: `aarch64-linux-android`, min SDK 28, target SDK 35.
- Last published signed Android versionCode: `16790002`. Future production code **must exceed both** this value and any newer APK already on the HONOR MagicPad 4.
- Exact owner-approved Pc launcher PNG SHA-256: `1a6495c214ae4536b432a34feff9b7001b612d4df1e79bf784b00d5b393f8a9b`.

## Feature-preservation checklist

The adapter remains the original released Android code, including TTF/OTF import and persistent custom fonts; shared SAF font folder; Android open/save and SAF round trip; JNI Activity and IME; keyboard modifiers; Touch Shortcut Pad; Help/update UI; graphics adapter diagnostics and CPU fallback; approved icon.

On v0.14 the six existing Android Type/Window/Help menu commands are reintroduced into a **temporary clone of exact official upstream source** with fail-closed unique-anchor checks. The previous v0.12 menu patch remains untouched. No changes to official source are committed here, and no claim of feature compatibility is made until ARM64 compilation and tablet checks pass.

## Test and release gates

1. `.github/workflows/photocraft-v014-compat.yml` must pass the source SHA/tag/workspace check, preservation markers and icon hash, Android update-policy and Java API-35 compilation, menu port and ARM64 Rust type check.
2. A **separately installed Test app** (`com.artcraft.photocraft.candidate`) may be compiled and signed with a new, disposable CI key. It is not a production update. Verify ABI, Java launcher, versionName, versionCode and temporary signature; keep APK in Actions artifacts, **not** GitHub Releases.
3. Test the candidate on HONOR MagicPad 4: reopen/export/save PSD and native files, font import/persistence, shared folder refresh and SAF permissions, physical keyboard shortcuts, touch shortcut pad, Pc icon, update checker, GPU info and CPU fallback. A successful cargo check is **not** device validation.
4. Only after all checks pass, create a separately reviewed **production-signing** build using the existing original PhotoCraft keystore and exact package `com.artcraft.photocraft`. Verify matching certificate fingerprint against the installed/published APK, increasing versionCode, correct versionName and unchanged APK SHA-256 before uploading a release. Do **not** extract or replace private signing keys.
5. Publish `photocraft-v0.14.0-android.1` to GitHub Releases only after full signing and upgrade verification. Do not uninstall the existing PhotoCraft app. Back up projects beforehand.

## Explicit exclusions

No scheduled upstream synchronization, automatic builds triggered by upstream releases, auto-merge, production signing, GitHub publication, Google Play, or updates to another ArtCraft app are enabled by this branch.
