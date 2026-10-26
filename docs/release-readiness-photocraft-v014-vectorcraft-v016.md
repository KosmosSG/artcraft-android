# PhotoCraft v0.14.0 / VectorCraft v0.16.0 — manual release authorization and gates

**Authorized by owner on 24 October 2026:** prepare and publish the next original-signed Android production releases on GitHub Releases **only after** completion of all release/update safety gates below. No Google Play. Do not turn on automatic upstream synchronization or auto-publishing. Do not repurpose temporary test signatures.

## Device acceptance (test-only packages)

| App | Source version | Reference | Device acceptance |
| --- | --- | --- | --- |
| PhotoCraft | v0.14.0-android.1 | [green test APK workflow](https://github.com/KosmosSG/artcraft-android/actions/runs/40060758110), draft PRs #23 and #28 | User reports installed and tested, looks good |
| VectorCraft | v0.16.0-android.1 | [green test APK workflow](https://github.com/KosmosSG/artcraft-android/actions/runs/40063409763), [green ARM64 source compatibility](https://github.com/KosmosSG/artcraft-android/actions/runs/40060937414), draft PRs #37 and #39 | User reports installed and tested, looks good |

**This is not production-update acceptance.** Both reviewed builds use separate test package identities and temporary signers; neither can replace an already installed production APK.

## Release gates (must be satisfied in order)

- [ ] Review stacked draft PRs and port only verified features into per-app release preparation branches, retaining official source pins and all Android-specific fonts, SAF, keyboard, touch, GPU, update UI and approved icons (launcher and top-left in-app).
- [ ] Fetch prior public APK assets from `photocraft-v0.12.0-android.1` and `vectorcraft-v0.14.0-android.5`. Record SHA256, versionName, versionCode, package ID, original certificate SHA256, and compare with owner-installed production app identities.
- [ ] Audit the actual production secrets and keystores **without exposing or rotating them**. PhotoCraft's `build-photocraft-release.yml` currently targets an older generic release path; VectorCraft's `vectorcraft-baseline.yml` is pinned to v0.14.0-android.2 and a legacy workflow branch. Do not run either unchanged as a new v0.14/v0.16 publisher.
- [ ] Reconcile PhotoCraft's original production signer and independently confirm VectorCraft's `VECTORCRAFT_KEYSTORE_BASE64`, `VECTORCRAFT_KEYSTORE_PASSWORD` and expected `VECTORCRAFT_CERT_SHA256`; fail closed if any is missing or differs from existing released signer.
- [ ] Produce ARM64 APKs using `com.artcraft.photocraft` and `com.artcraft.vectorcraft` (not `.candidate` or `.dialogtest`), preserving installed user data and private signing identity.
- [ ] Select reviewed versionCode values strictly greater than existing released APK **and actual installed APK** for each app. Confirm Android package and versionName match intended GitHub tag.
- [ ] Verify `apksigner` certificate fingerprint, APK launchable Activity, Java SAF bridge, ARM64 library, custom and shared font support, approved app/icon bytes, and build provenance with SHA256 sums.
- [ ] Perform **in-place update** on HONOR MagicPad 4 for each production-signed candidate. Confirm documents/settings/fonts persisted; verify release checker, optional updater panel/dialog, keyboard, exports, rotation and GPU diagnostic.
- [ ] Publish **manually** to GitHub Releases only after all above checks pass; attach the verified production APK, checksums, notes and correct app-specific tag. Never overwrite old release assets.
- [ ] Verify each in-app updater only surfaces the corresponding correct release.

## Invariants

- Distribution: GitHub Releases only. No Google Play.
- No automatic upstream sync, automatic publishing, uncontrolled mergers, or signing-key rotation.
- Test-only APKs must **never** be public production release assets.
- Existing versionCodes and signer fingerprints must be measured, not invented.
- This document is an authorization/verification checklist; it does **not** certify production readiness or imply a public release was published.
