# LightCraft official v0.17.0 — isolated source provenance and Android integration review (2026-11-02)

**Scope:** Review-only staging stacked on draft PR #107 and the approved Lc icon branch. No Android source port, build, signing, merge or publication.

## Verified upstream identity
- Official stable release: https://github.com/storytold/lightcraft/releases/tag/v0.17.0 (published 2026-11-01 19:27:20 UTC; neither draft nor prerelease).
- Direct Git tag `refs/tags/v0.17.0` resolves to `5a09d075306291a1522d5e8bb0710774f3733594`; `Cargo.toml` workspace version `0.17.0`, Rust MSRV `1.95`, repository `storytold/lightcraft`.
- Provenance check: `python3 tools/lightcraft/verify_v017_source.py /path/to/clean/tagged/lightcraft`; read-only and not an Android build.
- Relevant upstream changes: shared craft-update result dialog; Auto Import race fix; safer URL/HTTP and EXIF parsing; accessibility improvements; buffered RAF decode; crop, masking, catalog and export behavior changes. Audit Android-specific SAF import, photo catalog, colour/RAW pipeline, masks and update UI before porting.

## Preserve the approved Android baseline
- Preserve original owner-approved Lc icon asset `assets/lightcraft/lc-user-approved.png` (previously recorded SHA-256 `8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4`), adaptive icon masks, SAF, photo library/session, GPU/RAW/ICC/export paths, hardware shortcuts, and GitHub APK updater.
- The existing v0.11 Android adapter is not proven compatible with v0.17.0. Do not infer a full Android source migration from this lock. No blanket 4 GiB font scanner until text-rendering needs are reviewed.

## Blocked release gates
1. Review upstream v0.17.0 APIs/dependencies and port on a separate LightCraft integration branch while preserving Android-only code and artwork.
2. Run source identity helper, host RAW/colour/catalog/export regressions and Android integration tests; then compile a public unsigned ARM64 APK only if ready, without triggering private/quota-failing workflows.
3. Verify APK SHA-256, `com.artcraft.lightcraft`, ABI, monotonic versionCode, updater/assets and production certificate continuity.
4. Original permanent LightCraft keystore stays under owner control on HONOR Linux Lab; no GitHub private signing, auto-release, tags, auto-merge or Latest changes.
5. Require exact signed APK physical-device acceptance and separate explicit owner approval before production. Existing LightCraft public APK remains untouched.

This PR is **provenance-only**, not a tested, signed or installable Android v0.17.0 build.
