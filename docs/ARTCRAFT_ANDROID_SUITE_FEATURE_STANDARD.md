# ArtCraft Android Suite — Standard features for every Android app

**Owner requirement (23 October 2026).** Treat these as **mandatory, release-gated features** for every current and future app in the ArtCraft Android Suite, not as a statement that each app already works. PhotoCraft is the feature model; adapt to each app's actual UI, text/font engine and Android bridge instead of copying source blindly.

## Custom fonts

1. Import user-chosen .ttf / .otf fonts through the Android Storage Access Framework (SAF) without root; validate file type and sensible size limits, handle cancellation and provider errors, and never install fonts system-wide.
2. Support an optional SAF-selected shared folder (e.g., ArtCraft-Fonts), with persisted per-app read permission, explicit refresh, bounded traversal, safe font validation and app-private cache. Android SAF grants do not automatically transfer between app package identities.
3. Refresh the app's own available font catalogue or, if its engine cannot reload fonts while running, clearly state that a restart is needed. Verify newly imported fonts actually appear in editing controls and survive an app upgrade.
4. Do not bundle unlicensed user fonts or expose their contents in logs or release artifacts.

## Android GitHub update checker

1. Provide a **manual Check for Updates** command visible from Help, or an equally discoverable app-specific UI, plus an **opt-in** saved "Check at Startup" preference (disabled by default).
2. Check **the suite's public Android GitHub Releases**, never infer Android compatibility from desktop upstream tags. Parse app-specific release tags `<app>-vMAJOR.MINOR.PATCH-android.N`, select published non-draft, non-prerelease entries with the matching actual app APK asset, and compare versions numerically.
3. Restrict release navigation to the app-specific allowlisted GitHub release URL. Do not silently download, install, or replace an APK.
4. Give **immediate, non-floating visual feedback** ("Checking…", "Up to date", "Update available", "No published Android APK", errors). Always repaint/respond after Help menu clicks, bound network timeouts, prevent endless spinners, and offer a close/dismiss action without covering the design canvas.
5. Keep the original app ID, signing certificate, higher Android versionCode, app data, workspaces, and user-selected fonts on upgrade.

## Mandatory release proof

- Preserve each app's upstream source provenance and custom Android features.
- Document the app-specific feature implementation and automated regression checks. A source stub or check-box is not implementation proof.
- Verify Android ARM64 compilation, SAF picker/permission behavior, true font availability, API success/no-release/error states, app/version/ABI, trusted APK certificate and checksum.
- Use separate permanent signing identity and backed-up key per app; do **not** reuse another app's key.
- Verify an install-over-existing-app on the target HONOR MagicPad 4 before claiming device compatibility or full release readiness. Never uninstall a user's existing app as a test prerequisite.
- Public GitHub Releases only, no Google Play requirement. Publish only through an individually reviewed, permanently signed, fail-closed workflow. Publishing policy remains disabled in the central read-only manifest; a separate per-app workflow is required.

## Coverage

PhotoCraft, VectorCraft, DesignCraft, FilmCraft, EffectCraft, PDFCraft, WordCraft, DeckCraft, LightCraft, SoundCraft, CADCraft, FigCraft, and GridCraft, plus any future app added to the suite.

**GridCraft** is the public app name, despite earlier "ExcelCraft" conversational shorthand. The owner approved the new glossy green **Gc** app icon on 23 October 2026 (replacing the earlier Xc choice); use its exact uploaded PNG only after its SHA-256 is verified against the GridCraft source lock. Do not substitute Microsoft trademarks/assets.

This standard is a continuing requirement for future commits, upstream merges, branches, builds and releases, **not** permission to automatically synchronize upstream or publish unverified APKs.
