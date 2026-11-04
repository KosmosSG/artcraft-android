# DesignCraft v0.17.0 — isolated Android integration (TEST ONLY)

Protected published stable baseline: **designcraft-v0.12.0-android.9**.
Official source version: **v0.17.0**, exact upstream SHA `e79d682e02dc66f14370958b193bfa46072b2f41`.

Build command: `bash build-debug.sh -designcraft -designcraft-v017 -packagename=com.artcraft.designcraft.test -appname='DesignCraft Test'`.
Test app ID: `com.artcraft.designcraft.test`, separate from production `com.artcraft.designcraft`.
Candidate version: `0.17.0-android.1`. Generated Android builder key is temporary and is **not** the production certificate.

Integration uses the existing v0.16 Android preservation overlays (fonts 5,000 / 4 GiB,
SAF, Escape, T/V, D/C/S, approved glossy Dc brand, Android Tools and WGPU adapter)
adapted to the pinned official v0.17.0 checkout. All such features require
validation in the compiled candidate and on the HONOR MagicPad 4. No other
ArtCraft app is intentionally modified. The v0.12.0-android.9 release and data
remain unchanged.

Gates: first run v0.17 source tests, then a single opt-in ARM64 compile;
review the generated APK manifest/package/ABI/signature, boot and test UI/fonts/
shortcuts/input/updater on device. **No production signing, merge or publication
is authorized.** Do not suggest installing the debug APK as a stable upgrade.
