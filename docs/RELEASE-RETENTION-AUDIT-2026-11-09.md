# ArtCraft Android release retention — audit snapshot (2026-11-09)

**Status: REVIEW ONLY. No releases, release assets, tags, branches, secrets, or workflow runs have been deleted.**

Repository: `KosmosSG/artcraft-android`. Snapshot: 84 published/non-draft release objects. Proposed retention: 23 protected, 61 **candidates** for deletion. Of candidates, 21 are marked prerelease. Their combined asset size is about 5099 MiB, not GitHub Actions minutes.

## Non-negotiable conditions before any deletion

1. Merge and review the workflow corrections in this pull request; avoid cleaning releases while builds are running.
2. Test the affected workflow metadata and APK baseline selection. Keep an installed-app rollback APK, package identity, signing fingerprint and SHA-256 manifest before pruning.
3. Audit `gh release download`, direct release URLs, any active app updater, any external/private signing workflow, and legacy Android build branches. This list does **not** prove those external dependencies absent.
4. Keep all Git tags and commits, the original signing material and private signer repositories untouched. Delete release objects/assets only, and only after a separate explicit review.
5. Re-read the live release inventory immediately before cleanup: this file is a static snapshot and new published releases change the KEEP/DELETE boundaries.
6. Do not change/delete *any* release tagged below as KEEP. If a keep release is unexpectedly missing, STOP.

### Why the three extra protected releases matter

- `photocraft-v0.14.0-android.1` is an older original-key signed PhotoCraft APK. Modern PhotoCraft uses a distinct V2 certificate, so preserving an original-key download matters for migrations.
- `lightcraft-v0.11.0-android.8` is a production-signed preview specifically referenced in recent release signing verification.
- `pdfcraft-v0.12.0-android.1` is hard-coded as the prior APK in `.github/workflows/pdfcraft-iconfix-release.yml` (a legacy one-off workflow). Do not delete it until the workflow is retired or rewritten after review.

## KEEP — protected release tags

### photocraft
- `photocraft-v0.21.0-android.5`
- `photocraft-v0.20.2-android.2`
- `photocraft-v0.14.0-android.1`

### vectorcraft
- `vectorcraft-v0.14.0-android.13`
- `vectorcraft-v0.14.0-android.11`

### designcraft
- `designcraft-v0.17.2-android.5`
- `designcraft-v0.12.0-android.9`

### effectcraft
- `effectcraft-v0.21.0-android.15`
- `effectcraft-v0.16.0-android.8`

### lightcraft
- `lightcraft-v0.18.0-android.1`
- `lightcraft-v0.11.0-android.6`
- `lightcraft-v0.11.0-android.8`

### pdfcraft
- `pdfcraft-v0.19.0-android.6`
- `pdfcraft-v0.12.1-android.3`
- `pdfcraft-v0.12.0-android.1`

### wordcraft
- `wordcraft-v0.15.2-android.11`
- `wordcraft-v0.15.2-android.6`

### gridcraft
- `gridcraft-v0.16.1-android.4`
- `gridcraft-v0.16.1-android.3`

### deckcraft
- `deckcraft-v0.16.0-android.3`
- `deckcraft-v0.15.0-android.1`

### filmcraft
- `filmcraft-v0.17.0-android.1`
- `filmcraft-v0.10.0-android.5`

## CANDIDATES — release objects for later deletion, **not approved for automatic removal**

- `deckcraft-v0.14.1-android.16`
- `deckcraft-v0.14.1-android.17`
- `deckcraft-v0.9.0-android.2`
- `deckcraft-v0.9.0-android.3`
- `deckcraft-v0.9.0-android.4`
- `deckcraft-v0.9.0-android.4-dcs-fix`
- `designcraft-v0.12.0-android.2`
- `designcraft-v0.12.0-android.3`
- `designcraft-v0.12.0-android.4`
- `designcraft-v0.12.0-android.5`
- `designcraft-v0.12.0-android.8`
- `effectcraft-v0.16.0-android.2`
- `effectcraft-v0.16.0-android.3-preview.40284755992` (prerelease)
- `effectcraft-v0.16.0-android.3-preview.40289333285` (prerelease)
- `effectcraft-v0.16.0-android.3-preview.40326570342` (prerelease)
- `effectcraft-v0.16.0-android.3-preview.40341024386` (prerelease)
- `effectcraft-v0.16.0-android.3-preview.40345515710` (prerelease)
- `effectcraft-v0.16.0-android.4`
- `effectcraft-v0.16.0-android.5`
- `filmcraft-v0.10.0-android.2`
- `gridcraft-v0.11.1-android.2`
- `gridcraft-v0.11.1-android.4`
- `gridcraft-v0.11.1-android.4-ctrlw-dcs-fix`
- `gridcraft-v0.15.0-android.1-ctrlw-dcs-fix`
- `lightcraft-v0.11.0-android.3` (prerelease)
- `lightcraft-v0.11.0-android.4` (prerelease)
- `lightcraft-v0.11.0-android.5` (prerelease)
- `lightcraft-v0.11.0-android.7` (prerelease)
- `pdfcraft-v0.12.1-android.1`
- `pdfcraft-v0.12.1-android.2`
- `photocraft-v0.10.0`
- `photocraft-v0.10.0-android.2`
- `photocraft-v0.10.1`
- `photocraft-v0.10.2`
- `photocraft-v0.10.3`
- `photocraft-v0.10.4`
- `photocraft-v0.12.0-android.1`
- `photocraft-v0.12.0-android.2`
- `photocraft-v0.14.0-android.1-preview.40293846691` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40300751061` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40348951736` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40354111525` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40358277612` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40422186503` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40523180826` (prerelease)
- `photocraft-v0.14.0-android.1-preview.40530378907` (prerelease)
- `photocraft-v0.14.0-android.2-ai-v2-preview` (prerelease)
- `photocraft-v0.14.0-android.4`
- `photocraft-v0.14.0-android.4-ai-v2-fontscan-preview` (prerelease)
- `photocraft-v0.14.1-v2-preview` (prerelease)
- `photocraft-v0.20.1-android.10`
- `vectorcraft-v0.14.0-android.10`
- `vectorcraft-v0.14.0-android.5`
- `vectorcraft-v0.14.0-android.8`
- `vectorcraft-v0.14.0-android.9` (prerelease)
- `wordcraft-v0.14.0-android.8`
- `wordcraft-v0.15.2-android.2`
- `wordcraft-v0.15.2-android.3`
- `wordcraft-v0.9.0-android.3`
- `wordcraft-v0.9.0-android.4`
- `wordcraft-v0.9.0-android.6`

## Verification notes

- `.github/workflows/build-photocraft-release.yml` previously downloaded the repository-wide latest APK, which could belong to LightCraft or another app. The proposed fix pins selection to the newest published stable **PhotoCraft** tag and requires exactly one APK asset, rejecting missing/ambiguous baselines.
- `.github/workflows/auto-publish-test-prereleases.yml` previously fetched only the first 100 releases for its per-app signed-APK upgrade verification. The proposed change paginates release inventory.
- No APK is rebuilt or resigned by this cleanup preparation. Keep any branch-specific build requirements and in-app update checks unchanged.
