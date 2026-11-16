#!/usr/bin/env bash
# CADCraft secure one-command Codespaces release wizard.
# No key material or passwords may enter Git history, logs or release artifacts.
# User must personally download encrypted off-GitHub backup, save two passwords,
# and confirm before the public production release gate can be triggered.
set -Eeuo pipefail
set +x
umask 077

readonly REPO="KosmosSG/artcraft-android"
readonly BRANCH="feature/cadcraft-v0190-android15-production-20261116"
readonly TAG="cadcraft-v0.19.0-android.15"
readonly GATE="tools/cadcraft_publish_gate.txt"

fatal() { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }
for tool in bash gh base64 git keytool openssl mktemp; do
  command -v "$tool" >/dev/null || fatal "Missing $tool. Use the CADCraft Codespace on the dedicated branch."
done
root="$(git rev-parse --show-toplevel)" || fatal "Not inside the CADCraft checkout"
cd "$root"
[[ -f tools/cadcraft_codespaces_signing_setup.sh &&
   -f tools/cadcraft_publish_gate.txt ]] || fatal "CADCraft signing scripts missing in current checkout."

current_branch="$(git branch --show-current)"
[[ "$current_branch" == "$BRANCH" ]] ||
  fatal "Wrong branch ($current_branch). Open a Codespace on $BRANCH."
gh auth status >/dev/null 2>&1 ||
  fatal "Sign in to your GitHub account in Codespaces with: gh auth login"

if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  fatal "Release $TAG already exists. Do not rotate or overwrite the signer."
fi

printf '\n%s\n' 'CADCraft Android.15 — guided permanent-signing setup'
printf '%s\n' '1. Create a dedicated key in your private GitHub Codespace.'
printf '%s\n' '2. Download and separately save its ENCRYPTED backup outside GitHub.'
printf '%s\n' '3. Recover/verify it, configure Actions secrets, and request publication.'
printf '%s\n' 'Do NOT paste passwords, signing keys or recovery material in ChatGPT.'

if [[ ! -s CADCraft-signing-backup/CADCraft-PERMANENT-KEY.p12.enc ]]; then
  echo
  echo 'STEP 1: Prepare signer and encrypted backup.'
  bash tools/cadcraft_codespaces_signing_setup.sh prepare ||
    fatal "Preparation failed. No publication attempted."
else
  echo
  echo 'Existing encrypted backup found. It will NEVER be overwritten.'
  [[ -s CADCraft-signing-backup/CADCraft-CERT-SHA256.txt ]] ||
    fatal "Existing key backup has no certificate fingerprint. Inspect before proceeding."
fi

echo
echo 'STEP 2: Download the encrypted backup and public certificate fingerprint.'
echo 'Codespaces Explorer > CADCraft-signing-backup > right-click each file > Download'
echo '    CADCraft-PERMANENT-KEY.p12.enc'
echo '    CADCraft-CERT-SHA256.txt'
echo 'Keep BOTH passwords in your password manager, separately from the backup.'
echo 'Save the encrypted files to storage OUTSIDE GitHub/Codespaces.'
echo 'GitHub cannot recover your keystore from encrypted Actions secrets.'
echo
read -r -p 'After downloading and checking your backup, type BACKUP SAVED: ' downloaded
[[ "$downloaded" == "BACKUP SAVED" ]] ||
  fatal "No backup confirmation. Key remains encrypted in the Codespace; resume with this same script."

echo
echo 'STEP 3: Restore-check key and encrypt it into your GitHub Actions secrets.'
bash tools/cadcraft_codespaces_signing_setup.sh activate ||
  fatal "Activation failed. No release trigger attempted; resolve the error, then rerun this script."

echo
echo 'Verifying ONLY encrypted repository Actions secret names (not their values)...'
for name in CADCRAFT_KEYSTORE_BASE64 CADCRAFT_KEYSTORE_PASSWORD \
  CADCRAFT_KEY_ALIAS CADCRAFT_KEY_PASSWORD CADCRAFT_CERT_SHA256 \
  CADCRAFT_BACKUP_VERIFIED; do
  gh secret list -R "$REPO" --app actions --json name --jq '.[].name' |
    grep -Fxq "$name" || fatal "Missing Actions secret $name; release not triggered."
done

echo
echo 'STEP 4: Request the user-authorized permanent signing and publication.'
echo "Target: $REPO, $TAG, package com.artcraft.cadcraft."
echo 'The CI release gate will still fail closed on any certificate, package,'
echo 'APK, JNI, version, signing or checksum mismatch. Do NOT bypass those checks.'
read -r -p 'Type PUBLISH CADCRAFT ANDROID.15 to trigger the release workflow: ' approve
[[ "$approve" == "PUBLISH CADCRAFT ANDROID.15" ]] ||
  fatal "Publication not requested. Signing secrets remain configured; no trigger."

if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  fatal "Release appeared during setup. Refusing a duplicate release."
fi

# Trigger the pre-existing branch-scoped production workflow using an ordinary
# owner-authenticated GitHub Contents API push. No secrets or passwords are
# written into the publication gate, and the old branch HEAD is never rewritten.
gate_api="repos/$REPO/contents/$GATE"
old_sha="$(gh api -X GET "$gate_api" -f ref="$BRANCH" --jq '.sha')" ||
  fatal "Cannot read remote publish gate with your GitHub permissions."
[[ "$old_sha" =~ ^[a-f0-9]{40}$ ]] || fatal "Invalid remote publish gate blob SHA."

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
gh api -X GET "$gate_api" -f ref="$BRANCH" --jq '.content' |
  base64 --decode > "$tmp/gate" || fatal "Could not read publish gate content."
[[ -s "$tmp/gate" ]] || fatal "Remote publication gate is empty."
grep -Fq 'cadcraft-v0.19.0-android.15' "$tmp/gate" ||
  fatal "Unexpected publication gate contents; refusing release trigger."
printf '\nOwner downloaded and confirmed encrypted CADCraft key backup outside GitHub.\n' >> "$tmp/gate"
printf 'Owner authorized one-time stable release after GitHub Actions signer and APK verification.\n' >> "$tmp/gate"
# Certificate fingerprint is public identity, not secret. Its exact value
# is verified by the GitHub Actions production workflow.
encoded="$(base64 -w0 "$tmp/gate")"
commit="$(gh api -X PUT "$gate_api" \
  -f message="release(cadcraft): owner-backed-up signing key ready; trigger Android.15 publish" \
  -f branch="$BRANCH" \
  -f sha="$old_sha" \
  -f content="$encoded" \
  --jq '.commit.sha')" ||
  fatal "GitHub refused publication gate update. Signing secrets are safe; ask ChatGPT to re-trigger."
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || fatal "Publication gate did not return a commit SHA."

echo
echo "CADCRAFT PRODUCTION WORKFLOW REQUESTED via commit $commit"
echo "Open: https://github.com/$REPO/actions"
echo "Release target: https://github.com/$REPO/releases/tag/$TAG"
echo "The release is NOT yet published until GitHub Actions passes every gate."
echo "Tell ChatGPT 'CADCraft signing prepared, release gate committed' to verify the run."
echo "Keep the downloaded encrypted backup and BOTH passwords. Delete the Codespace after verifying the backup."
