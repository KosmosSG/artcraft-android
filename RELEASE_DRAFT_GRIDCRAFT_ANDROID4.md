# GridCraft v0.11.1-android.4 (ARM64) — GitHub release DRAFT

> **DRAFT — NOT PUBLISHED.** This is preparation for a native GitHub Draft Release, not a published/tagged release. Do not mark stable or publish before the locally signed APK and HONOR device tests have been checked.

## GitHub release form

| Field | Value |
| --- | --- |
| Tag | `gridcraft-v0.11.1-android.4` |
| Target (pin exact build source) | `c456e222a8cc5d812da54468af9758c3919b442f` |
| Title | `GridCraft v0.11.1-android.4 (ARM64)` |
| Release state | **Save draft**, not Publish |
| Set as latest release | Off |
| Pre-release | Consider enabling if publishing before device acceptance |

## Public-facing release notes (paste into description)

### GridCraft v0.11.1-android.4 (ARM64)

This Android update focuses on physical keyboard handling and safer spreadsheet save/close behavior while retaining GridCraft's existing font and tablet features.

**Changes**
- **Escape while editing:** Updated hardware ESC handling for cell, formula and text-box editing, without requiring a canvas tap to resume keyboard shortcuts.
- **Unsaved changes dialog:** Adds visible physical keyboard hints: **D** — Don't Save, **C** — Cancel and **S** — Save, with modal routing that takes precedence over sheet editing.
- **Save-before-close protection:** Android Storage Access Framework saves now wait for write acknowledgement; cancelled or failed writes should keep the workbook open, and edits made during an in-flight save are protected against closing.
- **Existing features retained:** Imported fonts, shared-font folder discovery, update-check feedback and approved GridCraft Gc artwork.

**Package details**
- Application ID: `com.artcraft.gridcraft`
- Version: `0.11.1-android.4`
- Version code: `16780036`
- ABI: `arm64-v8a`
- Production signing: same original GridCraft certificate as the published Android.2 release.

**Installation:** Install the verified original-key-signed APK over your existing GridCraft. Do not uninstall the existing application if retaining documents, settings and data.

**Testing scope:** GitHub ARM64 compilation, source checks and unsigned artifact checks passed. The owner signed the APK in Linux Lab and showed the original production certificate. Physical-device verification of ESC, D/C/S, workbook saves and font rendering should be completed before labeling this release stable.

## Attach exactly these files

- `GridCraft-v0.11.1-android.4-arm64-v8a.apk` — the locally **SIGNED** production-key APK, not the GitHub unsigned artifact.
- `SHA256SUMS.txt` — checksum of that exact signed APK.

The locally signed files currently reside on the owner's Linux Lab under `/home/honor/ArtCraft-Signing/publish/`; they have **not been uploaded** to this GitHub repository or GitHub Releases by this draft operation.

## Verification and publication checklist

- [x] ARM64 compile, isolated GridCraft Android.4 overlay and approved artwork checks passed: https://github.com/KosmosSG/artcraft-android/actions/runs/41084714179
- [x] Build version, package and code verified in CI and again with owner's local aapt output
- [x] Owner's local apksigner output matched original GridCraft certificate SHA-256 `09d292709d4dcce84a65e828bdd8a2ce93de62fa4dc6c584bd6269839da8090d`
- [ ] Run `sha256sum -c SHA256SUMS.txt` in the local publish folder, confirming OK
- [ ] Open the final signed APK on HONOR MagicPad 4 as an update; verify data retained and exercise ESC, D/C/S, saving, import fonts and spreadsheet reopen
- [ ] Upload **signed** APK and checksum to the native GitHub Draft Release
- [ ] Review notes, tag target and assets prior to any public publication
- [ ] Publish only upon the owner's approval and appropriate test acceptance

## Source and provenance

- GridCraft development PR #90: https://github.com/KosmosSG/artcraft-android/pull/90
- Exact compiled source: `c456e222a8cc5d812da54468af9758c3919b442f`
- Unsigned build workflow run: https://github.com/KosmosSG/artcraft-android/actions/runs/41084714179
- Previous published GridCraft release: https://github.com/KosmosSG/artcraft-android/releases/tag/gridcraft-v0.11.1-android.2

This draft document is informational. It does not create or modify a GitHub Release, release tag, APK, signing key, workflow or published asset.
