# FilmCraft Android v0.10.0-android.1 — production signing handoff

This is a **manual, fail-closed, FilmCraft-only** release path, not a published release or proof of device functionality.

## Existing verified candidate

- [Successful enhanced build #39789365991](https://github.com/KosmosSG/artcraft-android/actions/runs/39789365991), source branch `filmcraft-android-candidate`, commit `0e004059cc067915125656b61af88c2c8da0b52b`.
- APK artifact `filmcraft-0.10.0-android.1-EPHEMERAL-NOT-FOR-RELEASE` (seven-day retention). This artifact is **temporarily signed and never an installable update**.
- Upstream pinned `storytold/filmcraft` v0.10.0, commit `cdf43fd366e378da266cb6d3c94549a45244be1f`.
- Planned package `com.artcraft.filmcraft`, versionName `0.10.0-android.1`, provisional code `1000001`.
- The approved original Fc icon is at `assets/filmcraft/fc-user-approved.png` on the candidate branch. The candidate build copied it into launcher resources.

## Owner-only preparation before a permanent signed build

1. Audit any existing FilmCraft installations, signed APKs, versionCodes, and signing certificate fingerprints. **If FilmCraft has ever been signed for distribution, preserve that exact original key**, not a newly generated one. If no original identity exists, generate an independent FilmCraft PKCS12 signing keystore in a trusted local environment. Never reuse another Craft app's key.
2. Create an owner-controlled **private** `KosmosSG/filmcraft-signing-private` repository for encrypted backup and recovery instructions; retain an independent encrypted offline/offsite copy as well. Never commit a cleartext keystore, alias passwords or base64 keystore to public Git history, Issues or PR comments.
3. Add the following GitHub **Actions secrets** to `KosmosSG/artcraft-android` (Settings → Secrets and variables → Actions):
   - `FILMCRAFT_KEYSTORE_BASE64`: base64 of the entire original PKCS12 keystore (one line)
   - `FILMCRAFT_KEYSTORE_PASSWORD`: original store password
   - `FILMCRAFT_KEY_PASSWORD`: original signing key password
   - `FILMCRAFT_KEY_ALIAS`: alias in that keystore
   - `FILMCRAFT_CERT_SHA256`: trusted certificate fingerprint as 64 hexadecimal characters, without separators
   - `FILMCRAFT_BACKUP_VERIFIED`: `YES` **only after** the encrypted independent backup is successfully restored and certificate-checked
   - `FILMCRAFT_HISTORY_AUDITED`: `YES` **only after** existing signed APK/installed versionCode history is checked
4. Set the **highest previous FilmCraft versionCode** in workflow input. Use `0` only after checking that there truly was no previously installed or published FilmCraft. A new versionCode must be greater than that value. If existing FilmCraft has code >= `1000001`, **stop** and revise the candidate/version ledger instead of downgrading.
5. Launch Actions → `FilmCraft permanent signing and verified GitHub Release` → Run workflow, keeping `publish=false`. Set candidate run and SHA from above. The workflow verifies the source run, temporary APK package/ABI, signs with the dedicated certificate, verifies byte-identical application payload, outputs SHA-256, and retains the signed APK as a private-in-workflow artifact (not a public Release).
6. Physically install/test the **exact signed APK** on HONOR MagicPad 4. Test media playback/export, SAF file permissions, TTF/OTF import, shared font directory and persistence, stylus/keyboard, update button and startup opt-in. Save the APK SHA-256 and device test evidence in the FilmCraft app-specific suite feature contract.
7. Only after all feature statuses and APK SHA evidence satisfy `tools/suite_feature_parity.py --app filmcraft --signed-apk-sha256 <SHA>`, rerun workflow with `publish=true` and `device_tested_sha256` set to the actual tested signed APK digest. GitHub must refuse existing release tags.

Canonical release tag: `filmcraft-v0.10.0-android.1`; title: `FilmCraft v0.10.0-android.1`; APK asset: `FilmCraft-v0.10.0-android.1-arm64-v8a.apk`. GitHub Releases only, no Play Store.

**Important:** This manual workflow cannot publish without a confirmed permanent identity, backup, version history, exact APK-device verification, and source-feature audit. The successful ephemeral candidate cannot satisfy those checks by itself. The candidate artifact expires, so rerun a pinned review candidate rather than pretending that missing bits were tested.
