# ArtCraft Launcher production-signing and publication

The owner tested **ArtCraft Launcher v0.1.0-android.9** (isolated Android ARM64 candidate). The public release is **not yet published**. GitHub Actions run [43615228433](https://github.com/KosmosSG/artcraft-android/actions/runs/43615228433) stopped safely because the **dedicated launcher permanent signing secrets are not configured**.

Do not upload the disposable debug-signed Android.9 APK as a public production release. If the signer changes, Android refuses future in-place updates. Each app has its own dedicated signing certificate.

## Setup once (on a trusted computer or local Linux Lab)

Use the GitHub repository's **Settings → Secrets and variables → Actions → New repository secret**. Create a **new, unique key for ArtCraft Launcher**. Never commit the keystore or paste private key material in issues or chat.

The publication workflow expects these **six** repository secrets:

| Secret | Value |
|---|---|
| `ARTCRAFT_LAUNCHER_KEYSTORE_BASE64` | Entire dedicated PKCS#12 keystore encoded as one-line base64 |
| `ARTCRAFT_LAUNCHER_STORE_PASSWORD` | Keystore password |
| `ARTCRAFT_LAUNCHER_KEY_PASSWORD` | Private key password |
| `ARTCRAFT_LAUNCHER_KEY_ALIAS` | Alias inside the keystore |
| `ARTCRAFT_LAUNCHER_CERT_SHA256` | Certificate SHA-256, 64 hexadecimal characters with no colons |
| `ARTCRAFT_LAUNCHER_BACKUP_VERIFIED` | Literal `YES`, but **only after an encrypted, off-machine backup of the keystore and passwords has been verified** |

Example to generate a new dedicated key on Linux (this command prompts for a password; do not paste it in the shell history):

```sh
umask 077
mkdir -p "$HOME/.local/share/artcraft-launcher-signing"
cd "$HOME/.local/share/artcraft-launcher-signing"
keytool -genkeypair -storetype PKCS12 \
  -keystore artcraft-launcher-release.p12 \
  -alias artcraft-launcher \
  -keyalg RSA -keysize 3072 -validity 10000 \
  -dname 'CN=ArtCraft Launcher, O=KosmosSG'
```

Select a long unique password. This sample PKCS#12 file normally uses the same password for the key and keystore, so both password secrets may have the same **value** (they remain separate secret names). The commands below display the values you need locally; never paste them into a public repository:

```sh
base64 -w0 artcraft-launcher-release.p12 > artcraft-launcher-keystore-base64.txt
keytool -list -v -storetype PKCS12 -keystore artcraft-launcher-release.p12 \
  -alias artcraft-launcher | grep -m1 'SHA256:'
```

For `ARTCRAFT_LAUNCHER_CERT_SHA256`, remove the colons from the certificate fingerprint and keep all 64 hexadecimal characters. **Back up the original keystore file and its password to two secure, controlled locations** before setting `ARTCRAFT_LAUNCHER_BACKUP_VERIFIED=YES`. Delete unnecessary plaintext base64 exports after adding the secret.

## Publish once the signing secrets are ready

Open the [Publish owner-tested ArtCraft Launcher Android.9 workflow](https://github.com/KosmosSG/artcraft-android/actions/workflows/artcraft-launcher-release.yml), then use **Run workflow** on `main`.

It is pinned to:
- Test build run: [43613265715](https://github.com/KosmosSG/artcraft-android/actions/runs/43613265715)
- Reviewed candidate commit: `e52be4adf78f3a000b079c58aea6cf9d4e4604dc`
- Package: `com.artcraft.launcher`
- App version: `0.1.0-android.9`, versionCode `9`
- Release tag: `artcraft-launcher-v0.1.0-android.9`
- Published APK: `ArtCraft-Launcher-v0.1.0-android.9-arm64-v8a.apk`

The workflow verifies the successful candidate run and downloaded artifact, checks the SHA-256, confirms APK identity, signs with your dedicated keystore, checks the exact expected certificate SHA-256, compares signed and unsigned application payloads, creates a new `SHA256SUMS.txt`, and publishes **only if every prerequisite succeeds**. It refuses to overwrite an existing tag/release.

**Device migration:** existing Android.1–9 disposable test APKs use debug certificates that may differ from the production key. Before installing this first stable launcher, uninstall **ArtCraft Launcher only**. The 13 individual ArtCraft apps and their data are not removed. Later launcher stable updates reuse the same permanent key with increasing Android versionCode.

## Website and updates

The [ArtCraft Android downloads website](https://kosmossg.github.io/artcraft-android/) already has a featured ArtCraft Launcher section and automatically lists published `artcraft-launcher-vX.Y.Z-android.N` releases. The in-app self-updater recognizes the same release namespace and canonical ARM64 APK plus `SHA256SUMS.txt`.

Future stable launcher releases **must** retain the same package name and signing key, and increment versionCode. Never generate a new signing key for each release.
