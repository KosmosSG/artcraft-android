#!/usr/bin/env bash
# Standalone Android SDK build. No Gradle, ArtCraft editor source or production keys.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
SDK="$(printenv ANDROID_HOME || true)"
if [ -z "$SDK" ]; then SDK="$(printenv ANDROID_SDK_ROOT || true)"; fi
if [ -z "$SDK" ]; then SDK="/usr/local/lib/android/sdk"; fi
if [ ! -f "$SDK/platforms/android-35/android.jar" ] || [ ! -x "$SDK/build-tools/35.0.0/aapt2" ]; then
  SDKMANAGER="$(find "$SDK/cmdline-tools" -type f -name sdkmanager -print -quit 2>/dev/null || true)"
  if [ -z "$SDKMANAGER" ]; then echo "Android SDK manager not found"; exit 1; fi
  "$SDKMANAGER" --install "platforms;android-35" "build-tools;35.0.0" >/dev/null
fi
TOOLS="$SDK/build-tools/35.0.0"
ANDROID_JAR="$SDK/platforms/android-35/android.jar"
BUILD="$RUNNER_TEMP/artcraft-stylus-diagnostic"
OUT="$REPO_ROOT/output/stylus-diagnostic"
mkdir -p "$BUILD/classes" "$BUILD/dex" "$OUT"
javac --release 17 -classpath "$ANDROID_JAR" -d "$BUILD/classes" \
  "$ROOT/src/com/artcraft/stylusdiagnostic/MainActivity.java"
"$TOOLS/aapt2" link -o "$BUILD/base.apk" -I "$ANDROID_JAR" \
  --manifest "$ROOT/AndroidManifest.xml" --min-sdk-version 26 \
  --target-sdk-version 34 --version-code 4 --version-name "0.1.3-test"
"$TOOLS/d8" --min-api 26 --lib "$ANDROID_JAR" --output "$BUILD/dex" \
  "$BUILD"/classes/com/artcraft/stylusdiagnostic/*.class
(cd "$BUILD/dex" && zip -q -u "$BUILD/base.apk" classes.dex)
"$TOOLS/zipalign" -f 4 "$BUILD/base.apk" "$BUILD/aligned.apk"
# Disposable signing key: randomly generated and kept only in GitHub runner temporary storage.
PASS="$(openssl rand -hex 24)"
keytool -genkeypair -noprompt -keyalg RSA -keysize 2048 -validity 30 \
  -alias diagnostic -keystore "$BUILD/temporary-test-only.jks" \
  -storepass "$PASS" -keypass "$PASS" \
  -dname "CN=ArtCraft Stylus Diagnostic TEST ONLY"
APK="$OUT/ArtCraft-Stylus-Diagnostic-v0.1.3-TEST-ONLY.apk"
"$TOOLS/apksigner" sign --ks "$BUILD/temporary-test-only.jks" \
  --ks-key-alias diagnostic --ks-pass "pass:$PASS" \
  --key-pass "pass:$PASS" --out "$APK" "$BUILD/aligned.apk"
"$TOOLS/apksigner" verify --verbose --print-certs "$APK"
"$TOOLS/aapt" dump badging "$APK" | grep -E "^(package:|sdkVersion:|targetSdkVersion:)"
(cd "$OUT" && sha256sum "$(basename "$APK")" > SHA256SUMS.txt)
echo "TEST APK built: $APK"
du -h "$APK"
