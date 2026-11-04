VectorCraft v0.21.0-android.4 — one approved temporary-signed ARM64 test build
User-tested android.3 PASS: launcher icon, top-left Vc icon menu, font-folder UI responsiveness, check updates, startup update toggle. Preserve all.
User-tested android.3 FAIL: black screen between Android splash and native editor; incomplete font coverage after manual 128-file batches.
Apply Android 12+ system SplashScreenView exit hold through native editor ready; maroon splash theme with approved Vc icon and valid XML.
Automatically continue existing 128-file/64MiB bounded scan batches in one worker until folder completes, 5000 eligible files or cumulative 4GiB limit.
Treat SAF unknown file sizes (0/-1/null) as streamable with hard per-file budget; preserve cached fonts, progress spinner and async catalog.
Run preflight Python and JVM tests first; stop if tests fail; only one ARM64 disposable-key signed artifact (com.artcraft.vectorcraft.test).
Do not touch production keystore, stable release, signing, or publish a GitHub Release.

Retry preflight only after revealing JVM scanner stderr (previous 41804327817 stopped before SDK/compiler).

Corrected JVM test fixture: previously escaped newline hid scan invocation; scanner still bounded and automatic.
