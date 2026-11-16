#!/usr/bin/env bash
# Owner-operated on a TRUSTED local machine only. Never run in public CI.
# Generates and privately stores the first CADCraft production signer.
# The key NEVER enters the Git repository, GitHub Actions logs, or the chat.
set -Eeuo pipefail
umask 077

repo='KosmosSG/artcraft-android'
for cmd in keytool gh base64 sed tr; do
  command -v "$cmd" >/dev/null || { echo "Required command missing: $cmd" >&2; exit 1; }
done
gh auth status >/dev/null || { echo "Run 'gh auth login' first (repository admin access required)." >&2; exit 1; }

dir="$HOME/CADCraft-signing-backup"
key="$dir/cadcraft-production.p12"
mkdir -p "$dir"
chmod 700 "$dir"
echo "Keep a verified encrypted OFFLINE copy of $key and the signing password."
echo "Never share either key or password in chat, issues, commits, screenshots, or releases."
if [[ -f "$key" ]]; then
  echo "Reusing the EXISTING local CADCraft key. Never replacing the first release's signing identity."
else
  echo "Creating a new CADCraft-only PKCS#12 signing key."
fi

read -r -s -p 'Enter CADCraft signing password (12+ characters, save privately): ' pass
printf '\n'
[[ ${#pass} -ge 12 ]] || { echo 'Password too short.' >&2; exit 1; }
read -r -s -p 'Confirm signing password: ' again
printf '\n'
[[ "$pass" == "$again" ]] || { echo 'Passwords do not match.' >&2; exit 1; }
unset again
export CADCRAFT_KEYSTORE_PASSWORD="$pass"
export CADCRAFT_KEY_PASSWORD="$pass"
trap 'unset pass CADCRAFT_KEYSTORE_PASSWORD CADCRAFT_KEY_PASSWORD' EXIT

if [[ ! -f "$key" ]]; then
  keytool -genkeypair -noprompt -keystore "$key" -storetype PKCS12 \
    -alias cadcraft -keyalg RSA -keysize 3072 -validity 10000 \
    -dname 'CN=CADCraft Android, OU=ArtCraft, O=KosmosSG, C=MY' \
    -storepass:env CADCRAFT_KEYSTORE_PASSWORD \
    -keypass:env CADCRAFT_KEY_PASSWORD
fi
chmod 600 "$key"

cert="$(keytool -list -v -keystore "$key" -alias cadcraft \
  -storepass:env CADCRAFT_KEYSTORE_PASSWORD |
  sed -n 's/^[[:space:]]*SHA256: //p' | head -n1 |
  tr -d ':[:space:]' | tr '[:upper:]' '[:lower:]')"
[[ "$cert" =~ ^[0-9a-f]{64}$ ]] || { echo 'Signer certificate fingerprint unavailable.' >&2; exit 1; }
echo "CADCraft production PUBLIC certificate SHA256: $cert"
echo "PRIVATE KEY: $key (password is NOT printed)"
echo "Back up this key + its password to secure storage OFF this machine."
read -r -p "After confirming an offline recoverable backup, type exactly YES to set GitHub Actions signing secrets: " approve
[[ "$approve" == "YES" ]] || { echo "Secrets not uploaded; key remains local at $key."; exit 1; }

# gh secret set reads each value via stdin and encrypts it using GitHub's public key.
# Avoid --body arguments, plaintext env files, or verbose shell tracing.
base64 -w0 "$key" | gh secret set CADCRAFT_KEYSTORE_BASE64 --repo "$repo"
printf '%s' "$pass" | gh secret set CADCRAFT_KEYSTORE_PASSWORD --repo "$repo"
printf '%s' 'cadcraft' | gh secret set CADCRAFT_KEY_ALIAS --repo "$repo"
printf '%s' "$pass" | gh secret set CADCRAFT_KEY_PASSWORD --repo "$repo"
printf '%s' "$cert" | gh secret set CADCRAFT_CERT_SHA256 --repo "$repo"
printf '%s' 'YES' | gh secret set CADCRAFT_BACKUP_VERIFIED --repo "$repo"

echo "CADCraft secrets configured without printing private values."
echo "Tell ChatGPT only 'CADCraft signing secrets ready' — NEVER paste credentials."
