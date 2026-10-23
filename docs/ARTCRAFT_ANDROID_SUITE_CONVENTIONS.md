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

Historical note from the initial 21 October review: VectorCraft signing provenance was unresolved at that point. Consult the latest private signing records and verified runs before deciding its current status; never generate a replacement production key or assume PhotoCraft's key applies. Establish and verify its fonts/file/keyboard baseline before additional tablet enhancements. These conventions do not authorize changes to PhotoCraft branches, workflows or running builds from the VectorCraft workstream.

## Reconfirmed enhancement requirements — 22 October 2026

The user reconfirmed that the remaining PhotoCraft enhancements must be carried into its APK and applied throughout all 12 ArtCraft Android Suite apps wherever compatible with the respective project. Use the same review checklist for PhotoCraft, VectorCraft, DesignCraft, FilmCraft, EffectCraft, PDFCraft, WordCraft, GridCraft, DeckCraft, LightCraft, SoundCraft and CADCraft.

- **Fonts:** native TTF/OTF import with no floating Custom Fonts window, persisted custom fonts, bounded shared SAF font-folder access and refresh wherever the app has a text/font workflow.
- **Updates:** useful manual Check for Updates feedback and an optional persisted startup check; compare the installed Android versionCode against verified compatible release metadata and never offer a downgrade.
- **Keyboard:** physical keyboard shortcuts, customization where supported, correct left/right modifiers and focus reset, soft keyboard and IME. Preserve each app's own command model; Photoshop-style defaults apply to PhotoCraft, not automatically to unrelated apps.
- **Touch controls:** an optional docked Shortcut Pad with saved visibility where useful, suitable app-specific commands, adequate touch targets and scrolling, preserved canvas/document space, and modal/text-entry command guards.
- **Tablet input/layout:** assess and implement applicable adaptive layout, touch/gestures, mouse/trackpad and stylus behavior. Pressure, tilt, pen buttons and palm rejection require separate API and device evidence; do not claim unsupported capabilities.
- **Graphics and files:** truthful GPU diagnostics, compositor hookup and suitable CPU/Auto/GPU fallback where the renderer supports them; preserve SAF open/save/export, file associations and each app's document/media engine and import/export fidelity.
- **Branding:** package each app's exact approved glass icon, preserve its colours and lettering, and verify the actual packaged launcher resources.

For each feature, keep a per-app draft checklist with one of these explicit states: implemented with evidence; implemented awaiting validation; pending implementation/review; or not applicable/blocked with a concrete app-specific reason. Compatibility is a per-app decision, not permission to silently omit the feature. Update these records as the implementation progresses.

The next PhotoCraft combined-APK checklist is in [draft PR15](https://github.com/KosmosSG/artcraft-android/pull/15). Its passing source checks do not demonstrate APK packaging. Equivalent per-app evidence must tie the intended enhancements to the exact candidate source and APK, relevant regression checks and packaged resources. Keep automated checks separate from user tablet acceptance.

Retain every proven applicable enhancement through subsequent official upstream upgrades. A ready-to-install announcement still requires the established signing, reserved versionCode, source/hash/package/certificate and unchanged-payload gates. This requirement does not change signing identities, authorize merging drafts or activate unreviewed release workflows.

## Required Android references — 22 October 2026

The user explicitly requires both references to inform compatible enhancements across all 12 apps:

- [MostafaXS1/artcraft-android](https://github.com/MostafaXS1/artcraft-android), reviewed starting commit `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`: suite packaging, per-app adapters and shared Android integration.
- [morte2437/photocraft-android](https://github.com/morte2437/photocraft-android), reviewed `android-port` commit `71c919b768c6d70bc8231b92e3de6a81fb949996`: PhotoCraft Android UI/input reference, including touch controls, shortcut pad, pen handling, fonts and update UX for compatibility assessment.

Inspect actual app-specific code, licenses/notices and exact official release APIs before porting. The Mostafa builder is MIT; morte's README/NOTICE describe MIT OR Apache-2.0 with third-party notices. Preserve applicable attribution and check each copied component. README claims and available reference APKs do not prove our implementation or tablet behavior.

Official stable storytold tags pinned to immutable commits remain the app sources. Adapt compatible pieces to each app's command model, renderer and document/media workflows. Do not replace our apps with fork APKs, adopt their signing identities/update channels, or overwrite custom adapters wholesale. Preserve exact approved artwork, permanent certificates, package identity and all existing enhancements.

Use the per-app checklist above to record implementation, source tests, packaged APK evidence and device validation separately. Record concrete reasons for inapplicable features; retain proven compatible enhancements across future upstream updates.
