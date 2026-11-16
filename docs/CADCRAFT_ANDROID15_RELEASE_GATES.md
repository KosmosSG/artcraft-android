# CADCraft v0.19.0-android.15 — production signing and release gates

CADCraft is a **new** production Android application with package `com.artcraft.cadcraft`.
The previous working Android.14 test APK uses `com.artcraft.cadcraft.test` and a **different disposable per-run certificate**. The production APK installs separately; it does not replace the test package.

## User-tested baseline

- Android.14: HONOR Magic-Pencil 4s auto side-button wheel recognition passed on HONOR MagicPad 4.
- Android.15: retains the native input safety checks; removes all TEST-only manual renderer and diagnostic windows; retains a user-facing `Pair Stylus Button` fallback.
- The production release requires successful source, package ID, version, native JNI, signature, size and checksum checks. CI does not verify physical hardware.
- Preserve the 75% size, 85% opacity, Cc icon, Android updater, SAF DXF/DWG, physical keyboard D/S/C and system appearance features.

## Reusable signer — required

**Never publish a GitHub Release signed by a per-run disposable key.** It would make future Android upgrades impossible unless the key were recovered. The owner must privately back up and verify a CADCraft-only permanent keystore before enabling publication.

Required **repository Actions secrets**, configured under **Settings → Secrets and variables → Actions**:

| Name | Meaning |
| --- | --- |
| `CADCRAFT_KEYSTORE_BASE64` | Base64 encoding of the backed-up CADCraft-only keystore |
| `CADCRAFT_KEYSTORE_PASSWORD` | Keystore password |
| `CADCRAFT_KEY_ALIAS` | Alias of the signing key |
| `CADCRAFT_KEY_PASSWORD` | Password of the private signing key |
| `CADCRAFT_CERT_SHA256` | Expected public certificate SHA-256 fingerprint (64 hex characters, no colons) |
| `CADCRAFT_BACKUP_VERIFIED` | Literally `YES` after the owner verifies safe offline backup and recovery |

Store the keystore and credentials in an offline password manager or encrypted backup. Never paste the private key or passwords in an issue, chat, PR, code file or release artifact.

The isolated `.github/workflows/cadcraft-v0190-android15-permanent-publish.yml` workflow checks the secret gates and expected certificate **before compiling**. If the secrets are absent, it stops without signing or publishing. It never uploads signing-key bytes.

## Release identity

- Tag: `cadcraft-v0.19.0-android.15`
- Package: `com.artcraft.cadcraft`
- App Info `versionName`: `0.19.0-android.15`
- First official `versionCode`: `16782095` (increment the Android suffix for future releases)
- Artifact: `CADCraft-v0.19.0-android.15-arm64-v8a.apk`
- ABI: `arm64-v8a`
- Signed with the dedicated CADCraft certificate; APK Signature Scheme v2 required
- A successful run publishes only this exact release tag, never overwrites previous releases or modifies main or other apps.

The user authorized the five cleanup recommendations and publication on 16 November 2026. The release task must still stop on any failed technical gate or unavailable signing credentials.
