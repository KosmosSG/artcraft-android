# HOLD — PhotoCraft v0.14.0-android.3 stable release draft (NOT PUBLIC)

**Status:** Prepared for review only; **do not publish or mark Latest** until the nine-gate PR93 checklist is satisfied. Owner requested stable publication on 1 November 2026, but this is not proof of device acceptance or model-rights clearance.

## Proposed public title

PhotoCraft v0.14.0-android.3 — ARM64 stable (AI Tools)

## Proposed release notes (publish ONLY after gates pass)

PhotoCraft v0.14.0-android.3 combines the core photo editor with opt-in local AI background removal. The AI result is inserted as an editable layer with Undo/Redo support. The build retains PhotoCraft keyboard/ESC, File Open/Save, Import Fonts and Check for Updates behavior from the tested AI integration line.

AI background removal requires the user's own running Linux Lab U2NetP CPU service. The PhotoCraft APK does **not** contain or download U2NetP model weights. ComfyUI features beyond read-only diagnostics are not enabled.

**ARM64 only:** for supported Android devices including the HONOR MagicPad 4.

**Important signing migration warning:** this candidate uses the permanent PhotoCraft V2 certificate, **NOT** the original PhotoCraft production certificate. Android will not update an original-key PhotoCraft installation in place to this V2 release. **Back up projects and app-private data before any uninstall**; uninstalling can erase local app data. The new build uses the same V2 certificate and a greater Android versionCode than the AI V2 `android.2` preview, but in-place update **data preservation must be physically verified before this note is approved**.

**Commercial model/data rights:** remain under review. Do not assert the model, training data or commercial workflows have been cleared until separately verified.

## Internal immutable artifact verification (remove internal notes from public release)

- Exact reviewed source build: `8119bc9932a33f7481385ce2490c62d5dc53ee1c`.
- Unsigned ARM64 build: [Actions run 41277842399](https://github.com/KosmosSG/artcraft-android/actions/runs/41277842399), success.
- Private permanent V2 signed APK: [Actions run 41278752124](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41278752124), success.
- Private signing artifact ID: `13072650980` (**expires 8 November 2026**).
- Exact APK asset: `PhotoCraft-v0.14.0-android.3-ARM64-V2-SIGNED-STABLE-CANDIDATE-PRIVATE.apk`.
- SHA-256: `83bc37c497027bc09d34178b9dcfe52d9be6a5b6169236138b988072e354f6b2`.
- Package: `com.artcraft.photocraft`; versionName `0.14.0-android.3`; versionCode `16790006`.
- V2 signer SHA-256: `EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936`.
- Signed APK-to-APK identity, launcher, versionCode and ARM64 checks passed against the owner-tested AI V2 `android.2` prerelease. These checks alone **do not** establish successful device installation/data retention.
- AI U2NetP model weights are not packaged in this APK.
- [Nine-gate stable-release checklist](./photocraft-ai-v2-stable-checklist.json) is the authority. Source CI showing success is **not** publication authorization.

## Blockers requiring evidence

1. Owner acceptance of **this exact android.3 signed candidate**, not reused android.2 results.
2. Successful **on-device** V2-to-V2 in-place update with preserved test project and settings, without an unsafe downgrade.
3. Real Linux Lab/Android suspend-resume, cancel, server restart and prolonged request tests.
4. Model-weight and training-data licensing/provenance determination sufficient for intended stable/commercial distribution.
5. Explicit reconciliation of the later original-certificate / owner-only Linux Lab signing instruction with V2-signed GitHub candidate. The owner publication request alone does not resolve this.
6. Final validation of release title/tag, update-channel ordering, SHA256SUMS and new candidate release assets before posting stable/Latest.

**No stable tag, release, merge, signing-key rotation or public asset upload should be created from this draft while the above items remain pending.**
