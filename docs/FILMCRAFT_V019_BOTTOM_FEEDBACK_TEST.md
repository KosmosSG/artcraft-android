# FilmCraft v0.19.0 — PhotoCraft-style bottom feedback test

## User-approved UX
Following HONOR MagicPad 4 screenshots, align FilmCraft update/check/blocked/error
notifications with PhotoCraft's bottom-centered neutral-gray pill, including a
small Fc icon at left. Remove top-right transient notifications. Preserve the
existing full native Android download-progress dialog with percentage, MB,
Cancel and checksum-verification state.

## Source integration
- `filmcraft_features_v019_bottom_feedback.rs`: non-interactive
  `Align2::CENTER_BOTTOM` pill, 58-point bottom inset, compact rounded
  neutral styling, 4.5 second standard visibility (7 seconds for errors).
  Update and font results use the same pill.
- Rust no longer mirrors those transient messages into the upstream
  persistent bottom-left status line. Progress messages remain solely in
  Android's native download dialog, while errors and completion appear as
  a single bottom pill.
- `FilmCraftActivity.features.v019.bottom-feedback.java.inc`: suppresses
  the duplicate completion AlertDialog in the disposable test flavor.
  Future production-signed builds still require an explicit Install/Later
  choice and APK checksum/package/signing verification.
- `runtime_patch_v019_bottom_feedback.py`: installs the exact scoped overlays
  during a disposable-builder ARM64 compile. Production and other ArtCraft
  sources are not modified.
- `test_upstream_v019_bottom_feedback.py`: static guards, plus existing
  compiled APK native/Java feature verification, remain required.

## Device acceptance checklist
1. Install separately as `com.artcraft.filmcraft.test` (uninstall an older
   test flavor only if the disposable signing certificate conflicts). Never
   uninstall `com.artcraft.filmcraft`.
2. Fc > App Updates > Check for Updates: see a **bottom-centered Fc feedback
   pill**. No top-right toast and no duplicated persistent bottom-left result.
3. Fc > App Updates > Download Verified APK: retain the **native Android
   horizontal progress dialog** with percentage, bytes and Cancel.
4. Cancel then retry; verify integrity-check state and single bottom pill for
   completion, errors or a blocked install.
5. App Updates > Install Verified Download in the test flavor reports that it
   cannot install over the published package, in a **bottom** pill.
6. Regression check: grouped Fc menu, Appearance and hover, custom fonts,
   SAF media import/export, clip playback, timeline pan/zoom, D/C/S and ESC,
   10 Ctrl+Q cycles, resume, thermal/GPU fallback.

Stop before original-certificate permanent signing, merging or publishing.
