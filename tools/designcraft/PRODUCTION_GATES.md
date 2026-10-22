# DesignCraft production readiness gates

Candidate ARM64 build: https://github.com/KosmosSG/artcraft-android/actions/runs/39638563915 (successful). Candidate package: `com.artcraft.designcraft.candidate`, signed with a disposable CI certificate. Draft review: https://github.com/KosmosSG/artcraft-android/pull/13.

## Do not merge or publish automatically

1. **Icon:** The generated `tools/designcraft/make_icon.py` image is not the exact approved glass `Dc` PNG. The approved image must be integrated and verified in a rebuilt APK. Never claim parity until a pixel-accurate approved asset is packaged.
2. **Device:** Install the candidate separately on HONOR MagicPad 4 (MagicOS 10), back up documents, test cold launch, rotation, background/resume, open/save/export/reopen, custom keyboard shortcuts, touch pad, TTF/OTF import, shared SAF font folder, persisted permissions, font reload, updates UI, and GPU diagnostics. Record device outcomes rather than inferring them from CI.
3. **Signing:** `KosmosSG/designcraft-signing-private` currently contains only a README. Confirm no existing production certificate before generating a dedicated key. Keep keystore and passwords out of public commits and CI logs. Verify encrypted backup restoration and record the certificate SHA-256 fingerprint privately. Do not use PhotoCraft/VectorCraft keys.
4. **Production version:** Choose `com.artcraft.designcraft` with a versionCode higher than every existing signed production version. Never equate the candidate code 16800001 with a production release reservation.
5. **Updater:** Only offer production APKs with matching package, monotonic versionCode, expected signing certificate and official published release metadata. No silent installation, automatic production signing or publication.
6. **Promotion:** Only after verified tablet testing, icon approval, persistent signing, backup recovery and production updater checks. Keep both PR #2 and PR #13 in draft until gates are satisfied.

## Candidate changes from PhotoCraft

- Native Type menu: Import Font, Select Shared Font Folder, Refresh Shared Fonts.
- Native Help menu: Check for Updates and Update Settings.
- Startup shared folder restore with SAF permission; bounded scanner and staged font-cache replacement.
- Persistent optional touch shortcut pad, disabled while text editing.
- Production-updater gate for disposable-key candidate.

The candidate build passing confirms compilation and package checks, **not** successful tablet behavior or production readiness.
