# VectorCraft Android baseline status

This is preparation, not a completed APK build or a production update pipeline.

The isolated baseline workflow uses official storytold/vectorcraft v0.14.0 at ad0566943ab9741e6356bbc9b53c3cc09895068d, and Android builder reference ac54d62d9d2d6f663295a4afd8972a7a3e79f9af. It checks the release tag still resolves to that source commit. No shared adapter, PhotoCraft workflow, default branch or existing release is replaced.

Version metadata becomes 0.14.0-android.1 with a separately supplied, reserved versionCode. The native source's version is not rewritten. APK name: vectorcraft-0.14.0-android.1.apk. Never reuse the test fixture code from the unit tests as an actual reservation.

Push runs verification utility tests only. Manual builds require explicit previous and reserved version codes. The native build uses a disposable local candidate key; only an unsigned payload is transferred to the separate signing job. That job does not execute the official app or builder source. It requires VECTORCRAFT_KEYSTORE_BASE64 and VECTORCRAFT_KEYSTORE_PASSWORD secrets and VECTORCRAFT_CERT_SHA256 repository variable. The pinned builder assumes alias artcraftbuilder with matching key/store passwords; review actual existing key compatibility rather than rotating or replacing it. Never add keys/passwords to the repository or chat.

Signing identity and installation provenance remain unresolved. Do not run production signing until the existing VectorCraft APK/key has been identified, or a first installation and new permanent identity have been explicitly established. The workflow deliberately cannot generate a production signing key. Expected certificate, package com.artcraft.vectorcraft, explicit versionName/versionCode, launcher and ARM64 library are checked before an installable artifact is uploaded. Version monotonicity is checked against the supplied previous code; a verified inventory/reservation mechanism is still required for unattended releases.

Local validation: eight verification tests pass, including wrong signer/package/version, missing launcher/native library and unsigned signature failure rejection. The metadata overlay applies to the exact pinned builder, which passes Python compilation and shell syntax checking after overlay. This does not establish Android compilation or runtime compatibility.

Still required: compile the pinned official source against the reference builder; review and implement any missing direct font import and other enhancement overlays; verify installation, fonts/import, SAF open/save/export and physical/soft keyboard on device; assess tablet extras after the baseline. A successful APK metadata check alone does not establish these features. Automated upstream detection is handled by the existing suite task; release signing/publication remains gated by each app's reviewed pipeline. No release publishing or device installation is implemented here.
