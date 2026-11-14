#!/usr/bin/env bash
# Approved FilmCraft Android.8 -> production signer and new GitHub release.
# Private keys remain in GitHub Actions temporary storage; fail closed.
set -euo pipefail
umask 077
MODE="$1"
TAG=filmcraft-v0.20.1-android.8
TESTED_SHA=46a01ca4c593b452ce5e4fc20a4820a1371bca4e
ROOT="$ANDROID_HOME"
TOOLS="$(find "$ROOT/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -1)"
test -x "$TOOLS/apksigner" && test -x "$TOOLS/zipalign" && test -x "$TOOLS/aapt2"
test "$GITHUB_REPOSITORY" = KosmosSG/artcraft-android
test "$GITHUB_REF" = refs/heads/release/filmcraft-v0201-android8-production-20261114

if [ "$MODE" = preflight ]; then
  test -n "$GH_TOKEN"
  for name in KEYSTORE_BASE64 STORE_PASSWORD KEY_PASSWORD KEY_ALIAS CERT_SHA256; do
    case "$name" in
      KEYSTORE_BASE64) value="$KEYSTORE_BASE64" ;;
      STORE_PASSWORD) value="$STORE_PASSWORD" ;;
      KEY_PASSWORD) value="$KEY_PASSWORD" ;;
      KEY_ALIAS) value="$KEY_ALIAS" ;;
      CERT_SHA256) value="$CERT_SHA256" ;;
    esac
    test -n "$value" || { echo "::error::Missing FilmCraft permanent signing secret $name"; exit 1; }
  done
  [[ "$CERT_SHA256" =~ ^[a-fA-F0-9]{64}$ ]]
  [ "$BACKUP_OK" = YES ] && [ "$HISTORY_OK" = YES ] || {
    echo "::error::FilmCraft prior release policy requires verified signer backup and installation history"
    exit 1
  }
  gh api "repos/$GITHUB_REPOSITORY/actions/runs/43607946837" > "$RUNNER_TEMP/filmcraft-tested-run.json"
  python3 - "$RUNNER_TEMP/filmcraft-tested-run.json" "$TESTED_SHA" <<'PY'
import json,sys
j=json.load(open(sys.argv[1]))
if (j.get("conclusion"),j.get("head_sha"),j.get("head_branch")) != (
  "success",sys.argv[2],"feature/filmcraft-v0201-android8-project-hover-rebind-20261114"):
  raise SystemExit("STOP: reviewed FilmCraft Android.8 test run identity mismatch")
print("PASS: GitHub Actions tested candidate SHA and success verified")
PY
  if gh release view "$TAG" -R "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
    echo "::error::FilmCraft version tag already exists; refusing overwrite"
    exit 1
  fi
  mkdir -p prior
  gh release download filmcraft-v0.19.0-android.1 -R "$GITHUB_REPOSITORY" --pattern '*.apk' --dir prior
  [ "$(find prior -maxdepth 1 -name '*.apk' -type f | wc -l)" -eq 1 ]
  OLD_APK="$(find prior -maxdepth 1 -name '*.apk' -type f -print -quit)"
  "$TOOLS/apksigner" verify --verbose --print-certs "$OLD_APK" > "$RUNNER_TEMP/filmcraft-old-cert.txt"
  "$TOOLS/aapt2" dump badging "$OLD_APK" > "$RUNNER_TEMP/filmcraft-old-badge.txt"
  python3 - "$RUNNER_TEMP/filmcraft-old-cert.txt" "$RUNNER_TEMP/filmcraft-old-badge.txt" "$CERT_SHA256" <<'PY'
import re,sys
from pathlib import Path
c,b=Path(sys.argv[1]).read_text(),Path(sys.argv[2]).read_text()
m=re.search(r"certificate SHA-256 digest:\s*([a-fA-F0-9]{64})",c,re.I)
v=re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",b,re.M)
if not m or m.group(1).lower()!=sys.argv[3].lower():
  raise SystemExit("STOP: previous FilmCraft certificate differs from configured permanent certificate")
if not v or v.group(1)!="com.artcraft.filmcraft" or int(v.group(2))>=2001008:
  raise SystemExit("STOP: previous FilmCraft production package or version code incompatible")
print("PASS: previous release certificate, production package and monotonic code verified")
PY
  printf '%s' "$KEYSTORE_BASE64" | base64 --decode > "$RUNNER_TEMP/filmcraft-production.keystore"
  test -s "$RUNNER_TEMP/filmcraft-production.keystore"
  chmod 600 "$RUNNER_TEMP/filmcraft-production.keystore"
  exit 0
fi

if [ "$MODE" = publish ]; then
  test -s "$RUNNER_TEMP/filmcraft-production.keystore"
  SOURCE=filmcraft-builder/output/filmcraft-0.20.1-android.8-presign.apk
  test -s "$SOURCE"
  mkdir -p release
  TARGET=release/FilmCraft-v0.20.1-android.8-arm64-v8a.apk
  "$TOOLS/apksigner" verify "$SOURCE"
  "$TOOLS/zipalign" -P 16 -f 4 "$SOURCE" "$RUNNER_TEMP/filmcraft-aligned.apk"
  "$TOOLS/apksigner" sign --ks "$RUNNER_TEMP/filmcraft-production.keystore" \
    --ks-key-alias "$KEY_ALIAS" --ks-pass env:STORE_PASSWORD --key-pass env:KEY_PASSWORD \
    --out "$TARGET" "$RUNNER_TEMP/filmcraft-aligned.apk"
  "$TOOLS/apksigner" verify --verbose --print-certs "$TARGET" > "$RUNNER_TEMP/filmcraft-new-cert.txt"
  "$TOOLS/zipalign" -c -P 16 4 "$TARGET"
  "$TOOLS/aapt2" dump badging "$SOURCE" > "$RUNNER_TEMP/filmcraft-presign-badge.txt"
  "$TOOLS/aapt2" dump badging "$TARGET" > "$RUNNER_TEMP/filmcraft-signed-badge.txt"
  cmp "$RUNNER_TEMP/filmcraft-presign-badge.txt" "$RUNNER_TEMP/filmcraft-signed-badge.txt"
  python3 - "$RUNNER_TEMP/filmcraft-old-cert.txt" "$RUNNER_TEMP/filmcraft-new-cert.txt" "$RUNNER_TEMP/filmcraft-old-badge.txt" "$RUNNER_TEMP/filmcraft-signed-badge.txt" "$CERT_SHA256" "$SOURCE" "$TARGET" <<'PY'
import re,sys,zipfile,hashlib
from pathlib import Path
oc,nc,ob,nb,expected,src,out=sys.argv[1:]
def signer(path):
 m=re.search(r"certificate SHA-256 digest:\s*([a-fA-F0-9]{64})",Path(path).read_text(),re.I)
 if not m: raise SystemExit("STOP: certificate fingerprint missing")
 return m.group(1).lower()
def ident(path):
 m=re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",Path(path).read_text(),re.M)
 if not m: raise SystemExit("STOP: APK package metadata missing")
 return m.group(1),int(m.group(2)),m.group(3)
old,new=ident(ob),ident(nb)
if not (signer(oc)==signer(nc)==expected.lower()):
 raise SystemExit("STOP: signed APK certificate does not match existing FilmCraft")
if new!=("com.artcraft.filmcraft",2001008,"0.20.1-android.8") or new[0]!=old[0] or new[1]<=old[1]:
 raise SystemExit("STOP: FilmCraft production package/version cannot update previous release")
def payload(path):
 with zipfile.ZipFile(path) as z:
  return {n:hashlib.sha256(z.read(n)).digest() for n in z.namelist() if not n.startswith("META-INF/")}
if payload(src)!=payload(out):
 raise SystemExit("STOP: permanent signing changed application payload")
print("PASS: original FilmCraft certificate, upgrade version, byte-identical app payload")
PY
  (cd release && sha256sum FilmCraft-v0.20.1-android.8-arm64-v8a.apk > SHA256SUMS.txt)
  printf '%s\n' "$CERT_SHA256" > release/signing-certificate-sha256.txt
  cat > release/RELEASE_NOTES.md <<'EOF'
FilmCraft v0.20.1-android.8 — ARM64 Stable

Official upstream: storytold/filmcraft v0.20.1 (cedf0c9bd060eb06a977d532402be2097c9ebe42).
Owner-tested Android.8 code: 46a01ca4c593b452ce5e4fc20a4820a1371bca4e.
Package com.artcraft.filmcraft; versionCode 2001008.

- PhotoCraft-style stylus wheel, approved Fc logo and high-quality action icons.
- Wheel defaults: size 75%, opacity 80%.
- Real stylus hover before first touch and when opening/changing projects.
- 80ms real pen polling, native SurfaceView rebind and input-focus recovery.
- Verified in-app updater, font import/shared folders, keyboard D/S/C, touch/trackpad.
- Optimized ARM64 native binary (symbol stripping and thin LTO).

The owner tested and approved the separate-install Android.8 APK. The
production package is freshly rebuilt and signed with the existing FilmCraft
production key; device testing of this exact signed APK remains separate.
EOF
  (cd release && sha256sum --check SHA256SUMS.txt)
  if gh release view "$TAG" -R "$GITHUB_REPOSITORY" >/dev/null 2>&1; then
    echo "::error::FilmCraft release already exists; refusing overwrite"
    exit 1
  fi
  gh release create "$TAG" -R "$GITHUB_REPOSITORY" --target "$TESTED_SHA" \
    --title "FilmCraft v0.20.1-android.8 — Stable ARM64" \
    --notes-file release/RELEASE_NOTES.md \
    release/FilmCraft-v0.20.1-android.8-arm64-v8a.apk \
    release/SHA256SUMS.txt release/signing-certificate-sha256.txt
  gh release view "$TAG" -R "$GITHUB_REPOSITORY" --json url,assets
  echo "PUBLISHED FilmCraft $TAG; APK SHA-256 $(sha256sum "$TARGET" | awk '{print $1}')" >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
echo "Usage: permanent_sign_publish_android8.sh preflight|publish" >&2
exit 2
