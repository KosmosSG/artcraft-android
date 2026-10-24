# GridCraft Android — release readiness checkpoint (2026-10-24)

Scope: GridCraft only, GitHub Releases / direct APK distribution, HONOR MagicPad 4 (MagicOS 10, ARM64). No Google Play, automatic upstream synchronization, or changes to any other ArtCraft signing identity.

## Latest verified baseline
- Current PR: #25 (draft), `development/gridcraft-v0111-fonts-updates-20261023`.
- Official stable source pinned to `storytold/gridcraft@ac8da7d49cbeb4be6aa1ad5869f3d29fe2da8cd9` (v0.11.1).
- Last successful **candidate-only** compile: Actions run 39929493656, artifact `GridCraft-v0.11.1-EPHEMERAL-NOT-PRODUCTION`; output is a disposable-key `com.artcraft.gridcraft.candidate` APK, **not install-over compatible with a production app**.
- That successful candidate compiled commit `9b85f15e7a6df15c7b6fb042d882a7521919041b`, which is **eight commits behind** the reviewed branch head `479d8e0634b2b7f64f377a2121f7071843b506ed` immediately before this checkpoint. Latest dock/icon changes therefore require a fresh full build.
- A push to this file under `tools/gridcraft/` will request the existing candidate workflow. No production APK should be inferred from a green candidate run.

## Required blockers before production signing or publication
1. **Approved launcher original:** GitHub `assets/gridcraft/launcher-source.png` is absent. The lock expects `b8cd22fdf04da6dfe4da3cf818fc85763509f767b15c132f75784a1f0d03ae06` (1254x1254 PNG). A 2026-10-24 recovered library copy with the same name and 1254x1254 dimensions instead yielded SHA-256 `950cbbdc0e118c0668133fa5cce2d780b6acf78cf4bea7df7a777e6d7b0339d5`. **Never silently replace the recorded expected hash.** Obtain/check the unchanged approved source bytes or obtain explicit owner approval for repinning before icon packaging.
2. **Permanent signer:** `KosmosSG/gridcraft-signing-private` is private and contains `.github/workflows/bootstrap-gridcraft-signer.yml`, but its Actions history was empty at this checkpoint. No production JKS/certificate or recoverable backup is verified. Owner must set `GRIDCRAFT_BACKUP_PASSPHRASE` (strong, 24+ characters) in the **private repository Actions secrets**, save it offline, and manually dispatch the bootstrap workflow **only after confirming no existing GridCraft production key/installed identity**. Retrieve its encrypted backup, verify recovery independently, then record the public cert fingerprint. **Do not put passphrases, keystores or recovery materials in this public repository.**
3. **Versioning/identity:** No production `versionCode` reservation, existing production package/certificate continuity check, or exact final `versionName=0.11.1-android.1` verification exists. The candidate compiler reports `versionName=0.11.1`, which is not the desired production name. Do not promote/relabel a candidate APK.
4. **Device regression:** No recorded installation/open/save/reopen of real XLSX/CSV spreadsheets, formula recalculation, IME/hardware keyboard, SAF TTF/OTF font import + restart, shared font folder refresh, dock layout or manual/opt-in update-check testing on HONOR MagicPad 4. Include portrait/landscape and installed-app update path after the signer/versionCode are proven.
5. **Production build and release:** Create a separately gated, *manual* GridCraft-only signer/build workflow after key and icon verification. Verify ABI, package, stable source hash, production versionCode/versionName, embedded app icon, APK signing cert digest, SHA256SUMS and exact release-asset name `GridCraft-v0.11.1-android.1-arm64-v8a.apk`. Publish only after reviewed CI and owner device verification. Do not enable auto-release or upstream schedules.

## Recommended ordered execution
- Rebuild the current **candidate** branch and review CI/logs for the latest dock changes.
- Integrate the exact approved icon only after SHA-256 reconciliation.
- Bootstrap and externally back up the GridCraft-only permanent identity, with owner's consent/secure secret input.
- Prepare signed production test APK; run tablet and install-over tests.
- Publish a verified GitHub Release/tag `gridcraft-v0.11.1-android.1` only after all gates pass.

This checkpoint documents status, not release authorization.
