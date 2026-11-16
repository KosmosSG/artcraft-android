# CADCraft Android.15 — GitHub-only production-signing setup

**Goal:** Prepare the reusable **CADCraft-only** signing key for the first stable
`com.artcraft.cadcraft` release, preserving a recoverable **encrypted backup off
GitHub**. This procedure uses only **GitHub.com and GitHub Codespaces in the browser**.
There is no need to use Linux Lab, a local Java installation, or a local GitHub CLI.

**Existing verification:** CADCraft `0.19.0-android.15` clean test APK was built
successfully in Actions run
[43818339853](https://github.com/KosmosSG/artcraft-android/actions/runs/43818339853),
with clean wheel UI, required JNI symbols and installed versionName. The
Android.14 automatic Magic-Pencil recognition had passed the owner's device test.
The production attempt
[43818914435](https://github.com/KosmosSG/artcraft-android/actions/runs/43818914435)
was safely blocked before compilation because `CADCRAFT_KEYSTORE_BASE64`
was not configured. **No stable CADCraft release was published.**

## One-command guided setup (recommended)

Open [the CADCraft Android.15 branch](https://github.com/KosmosSG/artcraft-android/tree/feature/cadcraft-v0190-android15-production-20261116) and choose **Code → Codespaces → Create codespace on this branch**.

In the Codespaces terminal, run this **one** command:

```bash
bash tools/cadcraft_one_command_release.sh
```

This interactive wizard runs preparation, encrypted key backup and recovery verification,
secret activation, and the approved release trigger automatically. It stops at
the **three essential human security checkpoints**: choose two different
passwords, download the encrypted backup plus public fingerprint **outside
Codespaces**, and explicitly confirm the backup and publication. The script
will **not** bypass these checkpoints. You must personally ensure the downloaded
backup is safely stored; the Codespace cannot prove off-GitHub storage.

After the wizard reports a **publication gate commit**, GitHub Actions starts
the signed release workflow. Publication is **not** confirmed until the
[release workflow](https://github.com/KosmosSG/artcraft-android/actions)
passes and the exact tag exists. If GitHub authentication or write
permissions prevent the trigger, leave the key and backup intact and tell
ChatGPT what stage failed. Never paste passwords or key material.

The manual prepare/activate procedure below remains available if you prefer
to run each step separately.

---

## 1. Create a private GitHub Codespace

On GitHub, open the
[isolated CADCraft Android.15 branch](https://github.com/KosmosSG/artcraft-android/tree/feature/cadcraft-v0190-android15-production-20261116).

1. Click **Code → Codespaces → Create codespace on this branch**.
2. Wait for the browser-based Codespaces editor and terminal. The branch
   includes a devcontainer configuration with Java 21.
3. Make sure you are working in a **Codespace you alone control**. Do not
   grant Live Share, public ports, or co-edit access while handling keys.
4. The script requires a logged-in GitHub CLI. If `gh auth status` says you
   are not authenticated, run `gh auth login` and authorize your own account.
   A Codespaces token may lack permission to manage Actions secrets; if
   `activate` reports insufficient permissions, authenticate as the repository
   owner with `gh auth login` or `gh auth refresh -s repo`.

## 2. Prepare the signing key and encrypted backup

In Codespaces **Terminal**, run:

```bash
bash tools/cadcraft_codespaces_signing_setup.sh prepare
```

The script will ask for **two different passwords of at least 16 characters**:

- A permanent **CADCraft signing password**.
- A separate **backup encryption password** for recovery.

Save both in your own password manager, **not in any GitHub repository file,
chat, screenshot, issue, Actions workflow input, or comment**.

The script generates a dedicated 3072-bit RSA PKCS#12 signing key, encrypts
the backup with AES-256-CBC + PBKDF2 (350,000 iterations), immediately decrypts
and byte-compares it, and deletes the temporary plaintext copy.

It places only this encrypted backup file inside the Git-ignored Codespaces folder:

```text
CADCraft-signing-backup/CADCraft-PERMANENT-KEY.p12.enc
```

It also writes the public certificate fingerprint to
`CADCraft-signing-backup/CADCraft-CERT-SHA256.txt`.

**IMPORTANT — Download now:** In Codespaces Explorer (left file pane),
locate `CADCraft-signing-backup`, right-click
`CADCraft-PERMANENT-KEY.p12.enc` and choose **Download**. Save the downloaded
file **outside GitHub/Codespaces** on private secure storage (preferably
two independently recoverable copies). Download `CADCraft-CERT-SHA256.txt`
as well. Keep your two passwords separately.

Do **not** proceed if you have not downloaded a recoverable backup.

## 3. Activate the encrypted repository secrets

In the same Codespaces Terminal, run:

```bash
bash tools/cadcraft_codespaces_signing_setup.sh activate
```

Enter the **backup password** first to recover the encrypted file in temporary
storage; enter the **signing password** next so Java can check the certificate.
The script compares the certificate fingerprint with the original.

Only after you independently verify the downloaded file and securely store
both passwords should you type:

```text
OFFLINE BACKUP VERIFIED
```

The script configures the following GitHub **repository Actions secrets**,
encrypting values locally before upload:

- `CADCRAFT_KEYSTORE_BASE64`
- `CADCRAFT_KEYSTORE_PASSWORD`
- `CADCRAFT_KEY_ALIAS`
- `CADCRAFT_KEY_PASSWORD`
- `CADCRAFT_CERT_SHA256`
- `CADCRAFT_BACKUP_VERIFIED` = `YES` (set **last**)

Verify the **secret names** are present in
[Repository Settings → Secrets and variables → Actions](https://github.com/KosmosSG/artcraft-android/settings/secrets/actions).
GitHub will not display secret values after saving them.

**If the script fails**, do not paste error logs containing credentials and do
not manually publish a disposable-signed APK. Report only the failing stage
(`prepare`, `activate`, `gh auth`, or another non-secret error).

## 4. Request the controlled publication

Return to ChatGPT and say:

> CADCraft signing secrets ready. Please sign, verify and publish Android.15.

The existing [production release workflow](https://github.com/KosmosSG/artcraft-android/blob/feature/cadcraft-v0190-android15-production-20261116/.github/workflows/cadcraft-v0190-android15-permanent-publish.yml)
will then be retriggered **once** through the isolated publish gate.
It checks certificate SHA-256, package `com.artcraft.cadcraft`,
versionName `0.19.0-android.15`, versionCode `16782095`, ARM64,
JNI symbols, signature v2, ZIP integrity and SHA-256 before publishing
the new tag `cadcraft-v0.19.0-android.15`.

**No publication is authorized merely by running `prepare`.** The
production workflow remains locked until the verified backup and signing
secrets are configured. Do not use the existing `com.artcraft.cadcraft.test`
APK's temporary signing key for production.

## 5. Recover the permanent CADCraft key in the future

Keep the encrypted `.p12.enc`, BOTH passwords, and public certificate
fingerprint. If your Codespace is deleted, the signing key **cannot be
retrieved from GitHub Actions secrets**.

On a trusted Linux environment or a **new private Codespace**, restore the
encrypted backup file and run this with OpenSSL:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 350000 \
  -in CADCraft-PERMANENT-KEY.p12.enc \
  -out cadcraft-production-restored.p12
```

OpenSSL prompts for the **backup encryption password**. The restored PKCS#12
keystore uses your **separate signing password** and alias `cadcraft`.
Protect the restored plaintext key and remove it immediately when not needed.

After verifying the backup and GitHub secrets, **delete the Codespace**
to remove its ephemeral key material and stop any billable compute; do not
delete your offline backup or either password.

**Security caveat:** GitHub Codespaces is a cloud environment. The plaintext
key exists briefly inside your private Codespace during generation and
activation, and inside the protected production Actions runner during signing.
GitHub Actions secrets are encrypted storage, **not an offline backup**.
