# ArtCraft Android Suite: release and APK naming

This is the forward-looking convention for all 13 ArtCraft Android Suite app IDs.
The stable upstream project version and the Android port revision are **separate**.

| Surface | Required format | VectorCraft example |
| --- | --- | --- |
| Android `versionName` | `MAJOR.MINOR.PATCH-android.REVISION` | `0.14.0-android.2` |
| GitHub release tag | `appname-vMAJOR.MINOR.PATCH-android.REVISION` | `vectorcraft-v0.14.0-android.2` |
| GitHub release title | `DisplayName vMAJOR.MINOR.PATCH-android.REVISION` | `VectorCraft v0.14.0-android.2` |
| Published APK asset | `DisplayName-vMAJOR.MINOR.PATCH-android.REVISION-arm64-v8a.apk` | `VectorCraft-v0.14.0-android.2-arm64-v8a.apk` |

The `appname` in tags is lowercase (`photocraft`, `vectorcraft`, etc.).
The user-facing `DisplayName` retains normal branding/capitalization.
A stable official upstream tag may have a leading `v`; APK `versionName` does not.
`REVISION` starts at `1` and increases by one for each Android-only
change that needs an update: icon fixes, fonts, UI, keyboard, file handling,
update checks, packaging, or Android integration. Example:
`LightCraft v0.11.0-android.1` → `LightCraft v0.11.0-android.2`.
When **official stable upstream** advances, adopt the reviewed new upstream
version and start that series at `android.1`.

This rule applies to PhotoCraft, VectorCraft, DesignCraft, FilmCraft,
PDFCraft, WordCraft, DeckCraft, EffectCraft, LightCraft, SoundCraft,
CADCraft, FigCraft and GridCraft. GridCraft/ExcelCraft branding is **not yet
resolved**; publication must wait for a definitive app identity.

## Implementing in a build and release workflow

Use the shared checker before creating a release, for example:

```bash
python3 tools/artcraft_release_naming.py plan \
  --app photocraft --upstream v0.12.0 --revision 2
python3 tools/artcraft_release_naming.py verify \
  --app photocraft --upstream v0.12.0 --revision 2 \
  --version-name 0.12.0-android.2 \
  --tag photocraft-v0.12.0-android.2 \
  --title 'PhotoCraft v0.12.0-android.2' \
  --apk PhotoCraft-v0.12.0-android.2-arm64-v8a.apk \
  --previous-code 16790002 --new-code 16790003
```

An individual publisher must still **read actual APK metadata** (package ID,
`versionName`, `versionCode`, ABI and signing certificate fingerprint), use
a release tag scoped to its own app, verify the exact APK's checksum and
in-place upgrade compatibility, and check the in-app update parser supports
this tag and APK filename. It must verify the official upstream version and
pinned source used by the app; merely passing a string to the naming checker
does not prove upstream provenance. Do not infer Android `versionCode`
from a filename or reuse another app's signing identity.

Publish only after the app-specific signing, ownership and physical-device
release gates are satisfied. The shared checker and the suite CI only
validate **format**; they do not build, sign, approve or publish APKs.

## Existing and legacy releases

**Never rename, overwrite, or re-sign an existing published APK** merely to
fix spelling. The already published PDFCraft
`pdfcraft-v0.12.1-android.1` remains available and installable: that tag
was chosen for an Android-only icon update while PDFCraft upstream was still
v0.12.0. Treat it as a historical exception, *not* a newer official upstream
release. Its next in-place update needs a strictly higher Android
`versionCode` than the installed APK and an unchanged signing certificate,
irrespective of its corrected future `versionName`.

Likewise, prior PhotoCraft numeric-only releases and draft naming variants
are historical, not reasons to rename binaries or bypass version migration.
Before shipping any next-version series, confirm the in-app updater and its
version comparison will recognize `appname-vMAJOR.MINOR.PATCH-android.N`
with the same app's `DisplayName-v...-arm64-v8a.apk`, and never offer a
version-code downgrade. Rework older/manual workflows that still emit legacy
names as part of their **next separately verified build**.

This document and the shared suite naming checker leave all previously
published releases, APK signatures, private keys, encrypted backups,
installed app data, and public-release safety switches untouched.
