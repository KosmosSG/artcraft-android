# FilmCraft v0.19.0 — PhotoCraft-style download progress (test only)

## Reference and device report
On HONOR MagicPad 4, the v0.19.0 separate test APK's updater successfully
downloaded a verified release, but the only visible progress was a top-right
toast saying "Downloading FilmCraft: 48%". The user requested the PhotoCraft
download presentation instead.

The approved PhotoCraft reference is
`adapters/photocraft/java/com/artcraft/photocraft/Updater.java` at
`photocraft-v0.21.0-android.5`: a native Android dark AlertDialog with a
horizontal ProgressBar (range 0–1000) and Cancel button.

## Narrow v0.19 overlay changes
- `FilmCraftActivity.features.v019.photocraft-progress.java.inc` preserves the
  existing official-release metadata selection, DownloadManager, asset-size,
  SHA256SUMS and installed-certificate checks. It adds a main-thread Android
  native dialog with version, a horizontal bar, live percent/MB, and Cancel.
- After the transfer, the dialog shows an indeterminate integrity-verification
  message before dismissal. On success, a separate confirmation reports the
  verified APK. Only a future *production-signed* build may present Install
  and Later; the separately installed `com.artcraft.filmcraft.test` never
  offers to install into the published FilmCraft identity.
- The Cancel action sets an atomic flag checked by the worker; the DownloadManager
  job is removed and incomplete output discarded. No production keystore is
  accessed or persisted.
- `filmcraft_features_v019_photo_progress.rs` stops toast overlays for every
  download percentage while preserving errors, completion messages, other
  shortcut handling, and bottom status text.
- `runtime_patch_v019_photo_progress.py` stages these v0.19-only feature
  overlays into the disposable Android builder.
- Compiled-DEX and offline-contract checks require the new dialog handlers
  before an APK can be considered verified.

## Device test acceptance
1. Keep published `com.artcraft.filmcraft` installed. The APK uses separate
   `com.artcraft.filmcraft.test` with a disposable signer; uninstall only an
   earlier `.test` candidate if Android reports a signing mismatch.
2. Fc > App Updates > Check for Updates; then Download Verified APK.
3. Native dialog should read "Downloading FilmCraft <version>" and show a
   horizontal progress bar with percent and MB. No repeated progress toasts
   obscuring the timeline.
4. Tap Cancel partway through a download, then repeat the download. The worker
   must remove incomplete files and a restarted download must begin at 0%.
5. Let an intact download complete; the progress state changes to verifying,
   then a verified-download message appears.
6. The test flavor may download an official APK but MUST NOT install over the
   stable FilmCraft package.
7. Verify Fc menu, hover, fonts, SAF media import/export, preview/playback,
   timeline zoom/pan, ESC, Ctrl+W D/C/S, Ctrl+Q, app resume, and 165Hz adaptive
   behavior have no regressions.

**Stop gate:** Never permanently sign, merge or publish before test approval.
