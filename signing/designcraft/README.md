# Dedicated DesignCraft signing handoff

The owner confirmed this is the first DesignCraft Android build. No prior signing key needs migration. No permanent DesignCraft key has been generated yet.

## Required private channel

Create **KosmosSG/designcraft-signing-private**, visibility **Private**, initialized with a README, and grant the connected GitHub app access to it. Existing PhotoCraft/VectorCraft private repos must remain untouched.

The connected API currently supports repository file changes, PRs and builds but not creation of repositories or management of Actions secrets. This handoff needs GitHub's UI; no Terminal is required.

Once connected, install `bootstrap.yml` from this directory as `.github/workflows/bootstrap.yml` in the private repo's main branch. It is intentionally outside `.github/workflows` here and has an additional repository/private/main guard.

Before running it, store a strong independently backed-up passphrase (24+ characters) in the private repo's Actions secret `DESIGNCRAFT_RECOVERY_PASSPHRASE`. Keep the passphrase in the owner's password manager independently of GitHub. Do not paste it into a chat, repository file or PR.

## Bootstrap behavior

- Generates RSA 3072 PKCS12 identity, alias `designcraft`, dedicated production package `com.artcraft.designcraft`.
- Uses a random keystore password. Bundles it with the key only inside the encrypted backup.
- Encrypts with GPG AES256 using the recovery secret; decrypts to a temporary directory and compares the restored key, password and exported certificate.
- Commits only the encrypted backup, public certificate and identity/version ledger to the dedicated private repository. Refuses to replace an existing identity.
- Deletes unencrypted temporary material when the job finishes. Builds and upstream code never run in this key-creation job.
- The owner must also download `designcraft-backup.gpg` to independent storage and retain the recovery passphrase. Repository persistence alone is not an independent backup.

## Signing and publishing gates

The bootstrap establishes an identity; it does not build or publish an app. Add isolated signing only after the unsigned payload, package, version and ARM64 launcher/library have been checked. Compare every signed APK certificate against the pinned public fingerprint. Allocate a production versionCode greater than `highest_production_version_code` and all prior installed/released DesignCraft codes; reserve it before signing, never decrement/reuse it. VersionName follows official MAJOR.MINOR.PATCH-android.N. Increase N for enhancements; reset to 1 only for a new official core version while still increasing versionCode.

User tests must use a privately signed artifact with that permanent identity before publishing to the public repository. Record the exact tested commit, APK SHA256, certificate and versionCode. Public publishing must only accept that exact verified/tested artifact and must not rebuild it or mark a release as tested without the user's report. Preserve existing releases and never use a suite sibling's key. Upstream tracking proposes the next source pin for review and must never overwrite enhancements or bypass these gates.
