#!/usr/bin/env bash
# CADCraft permanent key bootstrap for a PRIVATE GitHub Codespace.
# No private keys/passwords are printed, committed, or uploaded as workflow artifacts.
# Two phases: prepare -> owner downloads encrypted backup -> activate.
set -Eeuo pipefail
set +x
umask 077
readonly REPO="KosmosSG/artcraft-android"
readonly TAG="cadcraft-v0.19.0-android.15"
mode="$1"
[[ "$mode" == "prepare" || "$mode" == "activate" ]] || {
  echo "Usage: bash tools/cadcraft_codespaces_signing_setup.sh prepare|activate" >&2
  exit 2
}
for cmd in git openssl keytool base64 sha256sum cmp mktemp; do
  command -v "$cmd" >/dev/null || { echo "Missing tool: $cmd" >&2; exit 1; }
done
root="$(git rev-parse --show-toplevel)"
cd "$root"
[[ -f tools/cadcraft_codespaces_signing_setup.sh ]] || {
  echo "Open the CADCraft Android.15 branch in GitHub Codespaces first." >&2; exit 1;
}
dir="$root/.cadcraft-signing-backup"
encrypted="$dir/CADCraft-PERMANENT-KEY.p12.enc"
fingerprint="$dir/CADCraft-CERT-SHA256.txt"
mkdir -p "$dir"
chmod 700 "$dir"

cleanup() {
  if [[ -n "$scratch" && -d "$scratch" ]]; then rm -rf -- "$scratch"; fi
  unset store_pw backup_pw check_pw CADCRAFT_STORE_PASSWORD
}
scratch=""
trap cleanup EXIT

if [[ "$mode" == "prepare" ]]; then
  [[ ! -e "$encrypted" ]] || {
    echo "An encrypted signing key backup already exists. REFUSING to replace it." >&2
    echo "Use 'activate' or inspect $dir; do not rotate the CADCraft signer." >&2
    exit 1
  }
  echo "Create TWO separate passwords, kept in your own password manager:"
  echo "  (1) Signing password for future CADCraft updates."
  echo "  (2) Backup encryption password for recovering the key."
  read -r -s -p "New signing password (16+ characters): " store_pw; printf '\n'
  [[ "$(printf '%s' "$store_pw" | wc -c)" -ge 16 ]] || {
    echo "Signing password too short" >&2; exit 1;
  }
  read -r -s -p "Confirm signing password: " check_pw; printf '\n'
  [[ "$store_pw" == "$check_pw" ]] || { echo "Signing passwords differ" >&2; exit 1; }
  unset check_pw
  read -r -s -p "Separate backup encryption password (16+ characters): " backup_pw; printf '\n'
  [[ "$(printf '%s' "$backup_pw" | wc -c)" -ge 16 ]] || {
    echo "Backup password too short" >&2; exit 1;
  }
  [[ "$backup_pw" != "$store_pw" ]] || {
    echo "Use a DIFFERENT backup password from the signing password." >&2; exit 1;
  }
  read -r -s -p "Confirm backup encryption password: " check_pw; printf '\n'
  [[ "$backup_pw" == "$check_pw" ]] || { echo "Backup passwords differ" >&2; exit 1; }
  unset check_pw
  scratch="$(mktemp -d "$dir/.temporary.XXXXXXXX")"
  export CADCRAFT_STORE_PASSWORD="$store_pw"
  keytool -genkeypair -noprompt -storetype PKCS12 \
    -keystore "$scratch/cadcraft.p12" -alias cadcraft \
    -keyalg RSA -keysize 3072 -validity 10000 \
    -dname "CN=CADCraft Android, OU=ArtCraft, O=KosmosSG, C=MY" \
    -storepass:env CADCRAFT_STORE_PASSWORD \
    -keypass:env CADCRAFT_STORE_PASSWORD >/dev/null
  cert="$(keytool -list -v -keystore "$scratch/cadcraft.p12" -alias cadcraft \
    -storepass:env CADCRAFT_STORE_PASSWORD |
    sed -n 's/^[[:space:]]*SHA256: //p' | head -1 |
    tr -d ':[:space:]' | tr '[:upper:]' '[:lower:]')"
  [[ "$cert" =~ ^[a-f0-9]{64}$ ]] || {
    echo "Could not validate signing certificate" >&2; exit 1;
  }
  # Pass encryption password on an anonymous file descriptor, not a process argument.
  openssl enc -aes-256-cbc -pbkdf2 -iter 350000 -salt \
    -in "$scratch/cadcraft.p12" -out "$encrypted" -pass fd:3 3<<<"$backup_pw"
  chmod 600 "$encrypted"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 350000 \
    -in "$encrypted" -out "$scratch/recovered.p12" -pass fd:3 3<<<"$backup_pw"
  cmp -s "$scratch/cadcraft.p12" "$scratch/recovered.p12" || {
    echo "Encryption/recovery verification failed." >&2
    rm -f "$encrypted"
    exit 1
  }
  printf '%s\n' "$cert" > "$fingerprint"
  chmod 600 "$fingerprint"
  sha256sum "$encrypted"
  echo
  echo "PREPARE COMPLETE: encrypted, locally decrypted, and byte-verified."
  echo "PRIVATE KEY IS NOT IN THE REPOSITORY OR ANY ACTIONS ARTIFACT."
  echo "NEXT: In Codespaces Explorer, right-click the file below and choose Download:"
  echo "  .cadcraft-signing-backup/CADCraft-PERMANENT-KEY.p12.enc"
  echo "Save it outside GitHub (secure offline/encrypted device backup)."
  echo "Save BOTH passwords separately; neither is recoverable from GitHub Secrets."
  echo "Then run: bash tools/cadcraft_codespaces_signing_setup.sh activate"
  exit 0
fi

# ACTIVATE: only after owner saved the encrypted backup outside Codespaces.
command -v gh >/dev/null || { echo "GitHub CLI 'gh' is required." >&2; exit 1; }
gh auth status >/dev/null 2>&1 || {
  echo "GitHub CLI needs login in this Codespace: gh auth login" >&2; exit 1;
}
[[ -s "$encrypted" && -s "$fingerprint" ]] || {
  echo "Missing encrypted backup. Run 'prepare' first, or restore both backup files to $dir." >&2
  exit 1
}
gh api "repos/$REPO/actions/secrets/public-key" >/dev/null || {
  echo "Your gh authentication lacks repository Actions-secrets write access." >&2
  echo "Run 'gh auth login' or 'gh auth refresh -s repo' with owner authorization." >&2
  exit 1
}
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  echo "Release tag already exists; STOP before changing an existing signer." >&2
  exit 1
fi
if gh secret list -R "$REPO" --app actions --json name --jq '.[].name' |
  grep -Fxq CADCRAFT_KEYSTORE_BASE64; then
  echo "Production keystore secret already exists; refusing to overwrite or rotate it." >&2
  exit 1
fi

read -r -s -p "Enter BACKUP encryption password: " backup_pw; printf '\n'
scratch="$(mktemp -d "$dir/.temporary.XXXXXXXX")"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 350000 \
  -in "$encrypted" -out "$scratch/cadcraft.p12" -pass fd:3 3<<<"$backup_pw" || {
  echo "Could not decrypt backup. Wrong password or damaged file." >&2; exit 1;
}
unset backup_pw
read -r -s -p "Enter CADCraft SIGNING password: " store_pw; printf '\n'
export CADCRAFT_STORE_PASSWORD="$store_pw"
cert="$(keytool -list -v -keystore "$scratch/cadcraft.p12" -alias cadcraft \
  -storepass:env CADCRAFT_STORE_PASSWORD |
  sed -n 's/^[[:space:]]*SHA256: //p' | head -1 |
  tr -d ':[:space:]' | tr '[:upper:]' '[:lower:]')" || {
  echo "Signing password was rejected." >&2; exit 1;
}
expected="$(tr -d '[:space:]' < "$fingerprint")"
[[ "$cert" =~ ^[a-f0-9]{64}$ && "$cert" == "$expected" ]] || {
  echo "Restored key certificate differs from the PREPARE certificate; STOP." >&2
  exit 1
}
echo "Verified recovered signing certificate fingerprint: $cert"
echo
echo "Before continuing, YOU must have downloaded the .p12.enc file to"
echo "a safe place OUTSIDE GitHub Codespaces and stored both passwords separately."
echo "Codespaces can expire; an Actions secret is NOT a recoverable signing-key backup."
read -r -p "Type exactly OFFLINE BACKUP VERIFIED to confirm: " confirm
[[ "$confirm" == "OFFLINE BACKUP VERIFIED" ]] || {
  echo "No secrets set; download and verify an offline backup first."; exit 1;
}

# gh secret set encrypts values locally; no plaintext key/password in any command
# argument, Git history, GitHub Action logs, or published artifacts.
base64 -w0 "$scratch/cadcraft.p12" | gh secret set CADCRAFT_KEYSTORE_BASE64 -R "$REPO" --app actions
printf '%s' "$store_pw" | gh secret set CADCRAFT_KEYSTORE_PASSWORD -R "$REPO" --app actions
printf '%s' 'cadcraft' | gh secret set CADCRAFT_KEY_ALIAS -R "$REPO" --app actions
printf '%s' "$store_pw" | gh secret set CADCRAFT_KEY_PASSWORD -R "$REPO" --app actions
printf '%s' "$cert" | gh secret set CADCRAFT_CERT_SHA256 -R "$REPO" --app actions
# Write backup gate LAST: partial failures cannot unblock production publishing.
printf '%s' YES | gh secret set CADCRAFT_BACKUP_VERIFIED -R "$REPO" --app actions

echo
echo "CADCraft permanent Actions secrets configured. Private values are NOT printed."
echo "Tell ChatGPT only: 'CADCraft signing secrets ready'."
echo "Keep the encrypted OFFLINE key backup and passwords for every future update."
