# PhotoCraft AI — 4 GiB shared-font scanning candidate

**Status:** PR #93 source staged; proposed **`v0.14.0-android.4`** *unsigned* ARM64 device-test candidate. It is **not** the previously owner-tested/signed `android.3` APK and is **not** a stable release.

## Capacity and behavior

- **Aggregate scan budget:** 4 GiB = `4,294,967,296` bytes of accepted TTF/OTF font files **per Refresh Shared Fonts scan**. This is scanned file data **on storage**, not application RAM and not a guarantee of free space.
- **Files per scan:** up to **5,000** eligible fonts (previously 200).
- **Individual font size:** retains **32 MiB** limit to prevent a single malformed or enormous file from exhausting resources.
- **Folders:** retains **up to 1,000 recursively visited SAF folders**, including child folders. The user must grant persistent read-only access with Android's folder picker; no all-files permission.
- **Copy:** Android streams font files in 64 KiB chunks into the app-private shared-font cache. Oversized/malformed/unreadable files are skipped; a revoked SAF permission is reported as an error without altering user documents.
- **Catalog:** PhotoCraft's engine now receives **cached file paths**; fontique registers path-backed font sources instead of eagerly reading all 4 GiB with `fs::read`. UI reports indexed path count, skipped count, and aggregate copied bytes. An available font's actual face may still need to load when first selected.
- **Limits:** 4 GiB is a maximum scan budget, **not a guaranteed number of usable font families**; invalid/unsupported fonts can be skipped. Available device storage, SAF provider speed, font parsing and Android memory may limit performance below 4 GiB. Old shared-font cache files are not yet guaranteed to be automatically pruned across different folder scans; monitor internal storage before importing huge libraries.

## Safety and verification

The read-only [source review CI](https://github.com/KosmosSG/artcraft-android/actions/runs/41295094924) passed with the pinned PhotoCraft Android baseline and official v0.14.0 font engine. It also checked the changed Java scanner against Android SDK 35 and parsed the Rust source. **This is source verification, not on-device proof of 4 GiB of fonts.**

A newly versioned [unsigned android.4 ARM64 candidate build](https://github.com/KosmosSG/artcraft-android/actions/runs/41295313087) is configured to apply this change after the tested PR93 AI overlay. The outcome must be checked; an unsigned build is not installable as a replacement for the permanent V2-signed app. No private keystore, model weights or stable GitHub Release are used by the public build.

## Device acceptance plan

1. Back up an existing PhotoCraft project, custom font imports and app data; preserve signed `android.3` before testing.
2. Sign the *exact* new ARM64 `android.4` candidate with the **approved permanent key** after reconciling the owner-only original-key vs V2 signing instruction. Confirm the package `com.artcraft.photocraft`, actual signed certificate and strictly increasing `versionCode`. Do not attempt installing an unsigned or disposable-key APK.
3. Test a modest collection first, then increasingly larger folders containing nested subfolders and multiple TTF/OTF families. Check that typed text and document rendering actually use newly discovered families; verify count and byte display.
4. Test restart/refresh after SAF grant, a revoked folder grant, invalid fonts, files above 32 MiB, and reaching the 4 GiB cumulative budget. Inspect storage and UI responsiveness before claiming full 4 GiB behavior.
5. Independently verify the V2-to-V2 in-place update retains projects, fonts, settings and shortcuts; check AI background removal and sidecar behavior again after the font-engine change.

**Release hold:** maintain PR #93 draft, unresolved AI model/data rights, signing policy and device stability gates. Do not overwrite already distributed `android.2`/`android.3` binaries or publish stable on the basis of code or synthetic CI alone.
