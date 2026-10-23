# ArtCraft Android Suite — PhotoCraft-style Custom Fonts & Check for Updates

**Status:** Suite-wide development/release requirement. The user requested that
every ArtCraft Android app preserve the established PhotoCraft custom-font and
update-checking experience. This is a persistent project rule for **all 13
registered apps**; it is NOT a claim that every currently published APK already
implements or passes these features.

Canonical machine-readable contract:
[configs/feature-parity.json](../configs/feature-parity.json).
Review/read-only audit: `python3 tools/suite_feature_parity.py`.
Future signed-APK release gate: `python3 tools/suite_feature_parity.py
--app APP --signed-apk-sha256 EXACT_SIGNED_SHA256`.

## Custom Font (every app)

- Support **TTF/OTF import** via Android's system file picker (SAF), keep
  imported fonts in app-private **persistent** storage and make them usable
  in the application's actual typography/text engine, not just visible in a
  selector. Check import, app restart and font selection.
- Provide optional **Select Shared Font Folder** through Android's system
  folder picker. Use read-only persisted SAF grants, traverse bounded nested
  folders, avoid broad storage access, and support **Refresh Shared Fonts**.
  Handle cancel, revoked provider grant, duplicates, corrupted files, huge
  files and restart without crashing or losing user documents.
- Where the app has a **Type** menu, place the font commands at its **bottom**,
  following existing upstream commands, separated appropriately. If an app
  has no Type menu, use its natural text/font menu with consistent labels;
  do not invent a nonfunctional Type menu.
- Keep existing upstream text rendering, document export, and platform-native
  font fallback intact. Font import is not the same as adding UI fonts only.
  Report unsupported font families or unsupported document embedding honestly.

## Check for Updates (every app)

- Expose **Help → Check for Updates** and **Startup Update Settings**
  immediately beneath **About AppName** within Help, when About is a dialog
  action (it is *not* an About submenu). If platform menu structure differs,
  preserve semantics with equivalent visible navigation.
- Check published (not draft) GitHub Releases in
  `KosmosSG/artcraft-android`. Filter for **this app's** release tags
  `appname-vX.Y.Z-android.N` and its exact signed APK asset. Support
  previous published legacy filenames if an installed older app requires one,
  without weakening the identity checks.
- Offer a persisted **Check for updates at startup** option, **OFF by default**.
  Manual checks always remain available. Startup/network errors never block
  opening or editing documents. Offline, rate limit and missing-release
  states should be understandable and nonfatal.
- Only announce genuinely newer versions: compare version and Android
  `versionCode`, verify app package ID and permanent signing certificate
  for any in-place update, check APK hash/metadata, and do not silently
  auto-install unsigned or unrelated APKs. The current safe baseline opens
  the matching GitHub Release/download in the browser, with user approval.
- Keep the suite's version naming
  `AppName vX.Y.Z-android.N`, tag `appname-vX.Y.Z-android.N`, primary APK
  `AppName-vX.Y.Z-android.N-arm64-v8a.apk`.

## Mandatory app-by-app implementation checklist

These are **required tasks**, not claims of completion:

1. Review the installed PhotoCraft implementation and its tested behaviors,
   including its release parser and source pinned to the actual signed APK.
   Do not assume the suite main PhotoCraft adapter contains every enhancement;
   release pipelines and private app branches may differ.
2. Implement or preserve app-native font import, persistent storage, the
   optional shared SAF font folder and refresh. Do not copy PhotoCraft's UI
   blindly if another app has a different document/font architecture.
3. Implement or preserve app-specific release filtering, manual and opt-in
   startup checks, version comparisons and update safety. Fix compatibility
   with already installed updater parsers before changing APK filenames.
4. Put font controls at the bottom of **Type** (when present) and update
   controls under **Help**, immediately below About. Keep every upstream
   command and PhotoCraft-style UI layout consistent.
5. Automated CI checks must cover source integration, Android package
   permissions, font persistence/error-handling, updater version/security
   filters, and release metadata.
6. Verify the **exact permanently signed APK** on target HONOR MagicPad 4:
   importing a TTF and OTF font, restarting, selecting/rendering fonts,
   choosing and refreshing a nested shared font folder, checking for updates
   manually, enabling/disabling startup checking and testing online/offline.
   Record the signed APK SHA-256 before declaring each capability
   `device_verified`.
7. Update `configs/feature-parity.json` feature statuses **only with
   supporting evidence tied to that APK**; do not mark them verified because
   the source compiled, a menu item exists, or an app in the same suite works.
   Re-verify when a later Android app revision alters fonts, menus, updater,
   signing metadata or package identity.

All apps currently have `not_verified` statuses in the shared contract to
avoid inventing device evidence. PhotoCraft is the behavioral reference named
by the user. WordCraft PR #11 already stages native TTF/OTF persistence, SAF
shared font-folder and update checking; these still need separate signed APK
and tablet verification. DesignCraft already has font/update integrations and
a published Android.2 release; the suite-wide feature gate should be adopted
and connected to its individual release workflow after verification. Do not
modify existing signed binaries merely to update this contract.

## Important release-safety boundary

This standard does not authorize unattended publishing or relax each app's
independent certificate, backup, versionCode, provenance or device-test gates.
The suite read-only CI validates that the policy is complete; **each actual
app publisher must explicitly integrate the per-APK feature gate** to block
release when required parity evidence is missing. A user may separately
authorize a clearly labeled untested release, but no tool may falsely record
it as device-verified.

Keep this document, contract and unit tests in `main` so every future
Craft app development and release can consult the same source of truth.
