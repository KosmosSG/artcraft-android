# EffectCraft Android permanent signing and release gate

Status (2026-10-22): **NOT ENROLLED; production release blocked**. Keep
`KosmosSG/artcraft-android/pull/6` in draft. The temporary candidate CI
key must never be promoted into an EffectCraft signing identity.

## Evidence and safety

- Public suite repository releases: none found during inspection.
- Accessible private signing repositories exist for PhotoCraft, VectorCraft,
  DesignCraft, WordCraft and LightCraft, but no EffectCraft-specific private
  signing repository was found. This does **not** establish that an EffectCraft
  key has never existed outside GitHub.
- The generic ArtCraft builder automatically creates
  `keys/artcraft-builder.jks`. It is not an authorized permanent EffectCraft
  key; do not publish candidate APKs built with it.
- Existing user-installed EffectCraft APK package ID, versionCode and certificate
  are still unknown. Do not silently rotate the signer or use the key of a
  different ArtCraft app.

## Website-only owner prerequisites

1. Check whether any installed or previously distributed EffectCraft APK exists.
   Record its package ID, versionName, versionCode and signing certificate
   SHA-256 (not passwords/private keys). An earlier production certificate must
   remain the signer for all in-place updates.
2. If and only if no dedicated key already exists, visit
   https://github.com/new. Select **KosmosSG**, enter
   `effectcraft-signing-private`, choose **Private**, and create the repository.
   Do **not** create a public signing repository.
3. In that private repository, open **Settings → Secrets and variables →
   Actions → New repository secret**. Create
   `EFFECTCRAFT_BACKUP_PASSWORD` using a new long random password kept
   exclusively in a secure password manager. Do not post it in a chat, issue,
   commit or workflow input. This is for encryption/recovery, not the same as
   PhotoCraft's backup password.
4. Only after the earlier-key check, add a reviewed, manually dispatched
   key-enrollment workflow in the private repository. Generate an independent
   RSA-3072 PKCS#12 key with alias `effectcraft` in the runner; immediately
   encrypt a backup containing the key and its password using
   AES-256/PBKDF2 (or stronger authenticated encryption), publish **only**
   the ciphertext as a short-retention artifact, verify recovery on a new
   runner, and record the public certificate fingerprint. Never print or
   upload plaintext key/password contents.
5. Download the encrypted backup and keep at least two offline copies,
   including an external drive stored safely, separate from the passphrase.
   GitHub Actions artifacts expire; they are not durable backups.
6. Use a dedicated EffectCraft-only GitHub Actions secrets/recovery workflow
   for release signing, with the certificate fingerprint pinned and checked
   before and after signing. The signing workflow must never read another
   ArtCraft application's keystore.
7. Preserve `com.artcraft.effectcraft` only if it matches any installed
   earlier package. The next versionCode must exceed every previously installed
   and distributed build. Signed APK updates require identical package and
   signing identity; changing them forces a separate install.
8. Gate public release on the real ARM64 compile, verified signature,
   manifest/version/ABI, bundled approved icon, SAF/font integration,
   in-app update behavior, actual device testing and explicit publication
   authorization. Publish under an EffectCraft-specific namespaced tag so
   another ArtCraft app's release cannot confuse the updater.

## In-app updater requirements

The updater must query EffectCraft-specific GitHub Releases (excluding draft,
prerelease, other apps and generic temporary-key artifacts), compare installed
version and Android revision, download only on request, verify package identity,
certificate and APK digest, then use Android's installer with consent. Never
uninstall existing data to update. Shared font grants and preferences must remain
in app-private storage under the same package identity.

## Current implementation evidence

- Candidate CI: https://github.com/KosmosSG/artcraft-android/actions/runs/39807477512
- Draft PR: https://github.com/KosmosSG/artcraft-android/pull/6
- Official upstream: https://github.com/storytold/effectcraft/releases/tag/v0.14.0

This document does not claim the key, backup, in-app updater or tablet tests exist.
