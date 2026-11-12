# Enhanced FilmCraft candidate

This candidate reuses PR7 fonts/shared-font-folder/updater source and the passing PR8 pinned build route. It does not merge either PR or change other apps.

- Official source v0.10.0: cdf43fd366e378da266cb6d3c94549a45244be1f.
- Android reference: ac54d62d9d2d6f663295a4afd8972a7a3e79f9af.
- Exact approved Fc original: assets/filmcraft/fc-user-approved.png, SHA256 242c40a9c5d508f75a771ece0cb8e4f741c914f7af20e46eb5e06f09e845764d (Glossy Glass F and C Icon(2).png). No recolour/redraw. The reference builder derives launcher resources from this source.
- Staging copies this branch's existing shared builder plus the FilmCraft-only runtime-overlay hook into a disposable checkout. This builder is not byte-identical to the pinned reference; no wholesale replacement is performed.
- Target ARM64, package com.artcraft.filmcraft, provisional 0.10.0-android.1/code1000001. Code is NOT a production reservation.
- Pull-request-only workflow, read-only token, no permanent secrets/key, no release/schedule. Uses unique temporary signer. Retains a seven-day NON-RELEASE inspection artifact only on success, then removes local key/output unconditionally.

Local workflow YAML/branch/permission/shell/cleanup checks passed. Existing static bridge/permission tests run again in CI before native compilation. Full enhanced APK compilation and Android behavior are pending until the actual run passes.

This is not a permanent-signed installable update. Tablet font/shared-folder, media playback/audio/export, SAF and keyboard validation remain necessary. Updater is a release-page checker, not verified APK installation. Permanent FilmCraft identity, prior version history and isolated signer/release metadata remain prerequisites. Do not install as an update or publish this temporary-key APK.

## 22 October build repair

Enhanced run [39712481559](https://github.com/KosmosSG/artcraft-android/actions/runs/39712481559) failed before native compilation: the icon diagnostic called relative_to(source) on the approved icon outside the source directory. Adopt the guarded diagnostic already present in the pinned Mostafa builder. Four regression cases exercise internal, absolute external, relative-source external and sibling-prefix paths. All pass locally, as do bash syntax and overlay static API/permission checks.

The attached-thread JNI helper now accepts jni::Env rather than the JNI 0.22 JNIEnv/EnvUnowned alias. This matches the attachment closure API; Android compilation remains pending. No FFI signature or production signing behavior changes.
