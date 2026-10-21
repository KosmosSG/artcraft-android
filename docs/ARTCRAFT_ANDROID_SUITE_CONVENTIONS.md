# ArtCraft Android Suite conventions

Agreed with the user on 2026-10-21. Apply to all upcoming ArtCraft Android Suite apps.

- Display version: `<official-version>-android.<revision>`.
- APK filename: `<appname>-<official-version>-android.<revision>.apk`.
- Example: `vectorcraft-0.14.0-android.1.apk`.
- Start Android revisions at `android.1` for each new official upstream app version.
- Increment to `android.2`, `android.3`, etc. for Android enhancements or fixes to that same upstream version.
- Always increase Android's internal versionCode across updates, even when the Android revision restarts for a new upstream version.
- Use official storytold app releases as app source. Review Android builder changes against MostafaXS1/artcraft-android commit ac54d62d9d2d6f663295a4afd8972a7a3e79f9af.
- Preserve existing enhancements, package identity, and signing certificates. Do not assume signing keys are shared between apps; establish a permanent key only after resolving whether an existing identity must be preserved.
- Keep each app's development isolated on its own branch and check existing branches/builds first.
- Preserve existing PhotoCraft releases, branches, workflows, and running builds. This document does not migrate or rename existing releases.
- VectorCraft baseline priority: fonts/font import, file open/save, and keyboard support; verify the APK and confirm device behavior before assessing additional tablet enhancements.

## Suite-wide Android enhancements and upstream automation

User confirmed on 2026-10-21 that Android enhancements are a suite-wide standard, not PhotoCraft-only. Review each applicable enhancement for every app, adapt it to that app's APIs and workflow, test it, and preserve it across official upstream updates. Do not claim feature parity before per-app validation.

Shared enhancement scope includes custom TTF/OTF font import and shared font folders where text/font workflows apply; Android SAF open/save/export and file associations; physical keyboard shortcuts and soft keyboard; tablet layout, touch, mouse/trackpad and stylus handling where supported; GPU diagnostics and appropriate CPU/Auto/GPU fallback; in-app update checks with useful feedback and preferences. Review additional compatible Android improvements from the pinned builder. Preserve existing app-specific improvements; do not remove an enhancement merely to make upstream compilation succeed.

Automation applies to PhotoCraft, VectorCraft, DesignCraft, FilmCraft, EffectCraft, WordCraft, LightCraft, PDFCraft, SoundCraft, DeckCraft, CADCraft and GridCraft. Reuse the existing ArtCraft upstream updates automation (six-hour checks), not duplicate watchers. Detect stable official releases, resolve exact commits, review compatibility and enhancement preservation, reuse isolated per-app branches, and avoid duplicate builds. Production signing/publication requires a reviewed per-app pipeline, preserved certificate, increasing versionCode and successful verification. Detection does not mean build, publication or device installation is complete. Android installation still requires user interaction.

VectorCraft signing provenance remains unresolved; do not generate a replacement production key or assume PhotoCraft's key applies. Establish and verify its fonts/file/keyboard baseline before additional tablet enhancements. These conventions do not authorize changes to PhotoCraft branches, workflows or running builds from the VectorCraft workstream.
