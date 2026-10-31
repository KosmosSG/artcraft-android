# PhotoCraft AI PR #93 — owner Linux Lab original-key signing handoff (31 October 2026)

**Status:** unsigned ARM64 input verified; **not signed, installable, approved for device installation or public release**. PR #93 remains DRAFT. This document is an evidence and owner-controlled signing handoff, not permission to publish or access signing secrets.

## Verified source and artifact

- PR: https://github.com/KosmosSG/artcraft-android/pull/93
- Exact compiled PR head: `fdc2b249ced6b52856a3d33c59f225de2a0ca30f`; this handoff documentation is a subsequent documentation-only change, not a new APK source build.
- Successful unsigned ARM64 build: https://github.com/KosmosSG/artcraft-android/actions/runs/41167324817
- Verified artifact: https://github.com/KosmosSG/artcraft-android/actions/runs/41167324817/artifacts/13030046136
- Artifact ID `13030046136`, 31,367,409 bytes, retention 7 days (download promptly). GitHub upload log reported artifact ZIP SHA-256 `784f2303944726dd4f1c5d9ed75f9ee7bc8e977397fed9d54c4cee0fe6ab03ea`; this is the ZIP digest, **not** the unsigned APK digest.
- Four artifact members: `PhotoCraft-v0.14.0-android.2-arm64-v8a-UNSIGNED.apk`, `SHA256SUMS.txt`, `UNSIGNED-VERIFICATION.json`, and `production-identity-build-proof.json`.
- The build job `124437597037` completed successfully at 2026-10-31 04:23 UTC; its exact step logs show ARM64/package/launcher/icon/version verification, ZIP local/central header consistency, unsigned signature rejection, successful disposable-key signability proof, deletion of the disposable-signed proof and key **before** uploading the four allowed files.
- Artifact contract: package `com.artcraft.photocraft`; label `PhotoCraft`; launcher `com.artcraft.photocraft.PhotoCraftActivity`; versionName `0.14.0-android.2`; versionCode `16790005`. The original public baseline `photocraft-v0.14.0-android.1` is versionCode `16790004`.
- Production certificate SHA-256 **must** equal `45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef`. A disposable-signed APK cannot update the owner's installed PhotoCraft.


### Optional safer ZIP handoff check (read-only, no Android SDK needed)

Before extracting the GitHub Actions artifact, run this script from the checked-out
PR93 source on Linux Lab. The artifact ZIP must be downloaded separately to the
local path shown; do **not** substitute an older preview or diagnostic artifact.

```bash
python3 tools/photocraft_ai_unsigned_artifact_verify.py \
  --zip /path/to/PhotoCraft-AI-unsigned-artifact.zip \
  --expected-source-sha fdc2b249ced6b52856a3d33c59f225de2a0ca30f \
  --expected-zip-sha256 784f2303944726dd4f1c5d9ed75f9ee7bc8e977397fed9d54c4cee0fe6ab03ea
```

The verifier checks the *exact* four-member allowlist, member safety, ZIP SHA,
APK SHA256SUMS, source identity, package/version and unsigned/disposable-key
deletion metadata. It never extracts, signs, installs or publishes the APK.
This is **metadata/integrity verification**, not cryptographic proof that the
APK is unsigned or signed with the permanent key. The original-certificate
and actual signed APK checks in steps 2–6 remain mandatory. The verifier has
a self-test: `python3 tools/photocraft_ai_unsigned_artifact_verify.py --self-test`.

## Owner-controlled Linux Lab procedure (no secrets in GitHub or chat)

1. Download the **unsigned** artifact ZIP, extract it locally, and compare `sha256sum -c SHA256SUMS.txt` against the extracted unsigned APK in the same directory. Check `UNSIGNED-VERIFICATION.json` reports `kind=UNSIGNED_SIGNING_INPUT_ONLY`, `source_checkout_verified=true`, `disposable_signability_test_passed=true`, `disposable_signed_apk_deleted=true` and `pr93_ci_commit=fdc2b249ced6b52856a3d33c59f225de2a0ca30f`. If any mismatch, **STOP**.
2. In the owner's Linux Lab signing manager, select the **existing original permanent PhotoCraft keystore** and its correct alias. Do not create, replace, rotate, reveal or upload a key. Verify the certificate fingerprint against the required value **before signing**. Password entry stays local in the manager.
3. Sign the extracted unsigned APK locally to a **separate private output file** using Android `apksigner` after any necessary `zipalign` step. Do not modify the input. Do not use a test/disposable key. Do not upload the resulting signed APK to public Actions or GitHub Releases.
4. On Linux Lab, use Android SDK Build Tools `apksigner verify --verbose --print-certs <private-signed.apk>` and `aapt dump badging <private-signed.apk>`. Verify **exactly one** expected signer certificate, the package, versionCode, versionName, PhotoCraft label and launcher. Never assume the keystore name proves certificate continuity.
5. Download the **actual published baseline** PhotoCraft APK from the public `photocraft-v0.14.0-android.1` GitHub Release, not an AI preview. With both signed APKs and Android SDK Build Tools available, run the repository's **read-only** compatibility gate:
   ```bash
   python3 tools/photocraft_ai_candidate_compatibility.py \
     --reference-apk /path/to/published-PhotoCraft.apk \
     --candidate-apk /path/to/private-PhotoCraft-AI-signed.apk \
     --candidate-tag photocraft-v0.14.0-android.2 \
     --aapt /path/to/android-sdk/build-tools/35.0.0/aapt \
     --apksigner /path/to/android-sdk/build-tools/35.0.0/apksigner \
     --output /path/to/private/photocraft-ai-compatibility.json
   ```
   The gate checks the real APK signatures, matching original certificate, package/version/launcher, ARM64 archive integrity and absence of bundled model weights or keys. **STOP** on any failure; do not install.
6. Only after passing the compatibility gate: back up the owner's PhotoCraft projects/documents, keep the existing installation in place, and perform an **in-place update** on HONOR MagicPad 4. Never uninstall to make a mismatched signer install. Recheck saved documents, fonts/SAF, updater, GPU diagnostics, blue Pc icon/name, ESC/V/T/C/Y/N shortcuts, local opt-in token consent, background removal, new layer, Undo/Redo, cancellation/close-dialog behavior and Linux Lab manual CPU sidecar startup. Owner must explicitly accept this exact signed candidate.
7. Final model-weight provenance/redistribution review and a **separate explicit publication approval** remain mandatory. Neither source CI nor a signed APK alone authorizes PR merge or release.

## Safety and coordination

Owner's 31 October policy supersedes the prior private GitHub signer authorization: production signing is performed by the owner in Linux Lab. **Do not rerun or auto-resume** private GitHub signing even if private runner availability changes. Private runner failures are not blockers for the owner's local path, but original-key availability/continuity and owner device testing remain unverified.

Historical ARM proof run #4 `41032183666` is completed/failed, not running. Its potentially disposable-signed diagnostic artifact `12966638625` still exists and requires the previously requested owner deletion; never install or redistribute it. The separate public proof #5 produced metadata only and deleted the disposable APK. Model weights are not bundled in the current APK; exact third-party weight redistribution rights remain open.

**Hard stop:** no PR merge/ready-for-review, main edits, key or secret access, public/pre-release, distribution of a production-signed APK, device install, or automation change without separate owner authorization.

## 31 October 2026, 15:32 MYT — ambiguous unsigned artifact JSON rejected

- **Reproduced safety gap:** Python's default `json.loads` accepts duplicate JSON object keys and silently uses the last value. A fabricated `UNSIGNED-VERIFICATION.json` with an initial `"production_signed": true` followed by the expected `false`, or a build proof with conflicting `proof_signer_matches_public`, previously passed the metadata checks. Different JSON consumers could disagree on the same ZIP. This is a verifier hardening issue, **not evidence that the verified GitHub artifact was tampered with**.
- **PR93-only fix:** [`0306a59b`](https://github.com/KosmosSG/artcraft-android/commit/0306a59b90114d69debbed25a539eda2279bdcaf) rejects duplicate keys in either metadata document (including nested JSON objects). Added two fail-closed regression fixtures; total negative checks increased from 9 to 11.
- **Verified no-APK CI:** [artifact-safety run #41180973328](https://github.com/KosmosSG/artcraft-android/actions/runs/41180973328), job `124478127552`, **PASS**: 3 existing static safety tests, unsigned ZIP verifier self-test, 11 rejection scenarios. Full job log inspected; **zero uploaded artifacts**. No signing, production key access, Android build, installation or publication.
- **Existing unsigned APK unchanged:** [run #41167324817, artifact #13030046136](https://github.com/KosmosSG/artcraft-android/actions/runs/41167324817/artifacts/13030046136) was compiled from `fdc2b249ced6b52856a3d33c59f225de2a0ca30f`. This subsequent Python-only verifier change does not require a new heavy ARM64 build. The pinned ZIP SHA-256 and APK SHA256SUMS remain mandatory checks.
- **Owner-only Linux Lab original-key signing** remains the current policy; never auto-resume private GitHub signing. Require exact original certificate SHA-256, read-only candidate compatibility, backup and in-place HONOR MagicPad 4 owner acceptance. Historical failed proof #41032183666 and its potentially disposable-signed diagnostic artifact #12966638625 remain a separate deletion concern. Model-weight redistribution rights and final publication approval remain open. PR #93 stays DRAFT.
