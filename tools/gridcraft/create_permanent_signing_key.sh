#!/usr/bin/env bash
# GridCraft one-time permanent signing identity setup.
# Run interactively in GitHub Codespaces; never commit or upload the .jks to this public repository.
set -euo pipefail
umask 077
if ! command -v keytool >/dev/null 2>&1; then
  echo "Java keytool is missing. Install a JDK before running this helper." >&2
  exit 1
fi
output_dir="${HOME}/gridcraft-signing-private"
keystore="${output_dir}/gridcraft-release.jks"
mkdir -p "${output_dir}"
chmod 700 "${output_dir}"
if [[ -e "${keystore}" ]]; then
  echo "Existing GridCraft keystore found at ${keystore}; refusing to replace it." >&2
  exit 1
fi
echo "Creating a dedicated GridCraft signing identity outside the repository."
echo "You will enter passwords into keytool's interactive terminal, NOT GitHub source code."
keytool -genkeypair -v \
  -keystore "${keystore}" \
  -storetype PKCS12 \
  -alias gridcraft \
  -keyalg RSA -keysize 3072 -validity 10000 \
  -dname "CN=GridCraft Android Release, OU=ArtCraft, O=KosmosSG"
chmod 600 "${keystore}"
echo
echo "Certificate details (share only the public SHA-256 fingerprint, never passwords):"
keytool -list -v -keystore "${keystore}" -alias gridcraft
echo
echo "Created: ${keystore}"
echo "IMPORTANT: Export this file from Codespaces and save at least one VERIFIED,"
echo "encrypted offline backup BEFORE deleting this Codespace."
echo "Do NOT commit this file, store your password in shell history, or add GitHub"
echo "secrets until the production workflow documents its exact expected secret names."
