# PhotoCraft AI PR #93 — production update readiness (not a release)

**Owner-device milestone:** PhotoCraft AI Preview ARM64 run #53 compiled successfully;
the owner tested U2NetP background removal, a new raster layer, Undo/Redo,
cancellation, dialog close, and existing physical-keyboard behavior on
HONOR MagicPad 4. Preview package is `com.artcraft.photocraft.ai.preview`,
signed with a disposable CI key. It cannot update or replace the normal app.

## Existing public PhotoCraft — verified reference

| Item | Release identity |
|---|---|
| Published tag | `photocraft-v0.14.0-android.1` |
| Android package | `com.artcraft.photocraft` |
| App label | `PhotoCraft` |
| Version | `0.14.0-android.1` |
| Version code | `16790004` |
| Signing certificate SHA-256 | `45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef` |

This public certificate **fingerprint** is not the secret signing key. The
`PhotoCraft AI production signing reference (read-only)` workflow verified
the APK using Android build tools; it does not grant access to private keys.

## New build-only source integration proof (PR #93)

`.github/workflows/photocraft-ai-production-dryrun.yml` starts from the
immutable, previously owner-tested Android source and injects the PR93 AI
modules. It converts only the **throwaway Actions workspace** from the
separate preview package to the real `PhotoCraft` label, package and Java
Activity namespace. It proposes `0.14.0-android.2` for **identity testing**
and carries forward the approved launcher and keyboard baseline.

The generic builder signs with a randomly generated **disposable** key.
It is therefore **not a production signing step**. The pipeline must confirm
that signer differs from the public release, verify the package, launcher,
version code, ARM64, approved icon and compiled code, then **delete the APK**.
Only a JSON proof is uploaded; never upload the disposable-signer APK with
the production package name. Failure at any gate must stop the proof.

**No Workflow Dispatch input enables publishing or production signing.**

## Separate eventual production-signed candidate — blocked until approved

1. Retrieve the original PhotoCraft permanent signing key through the
   owner's **trusted private** GitHub Actions signing environment. Never
   expose a JKS, key password, base64 key, or signing secret in chat,
   ordinary artifacts, logs or the public PR. Do not create a replacement
   permanent key, overwrite existing signing secrets, or use the generic
   builder's disposable key for this update.
2. Build the same reviewed AI source with a version code **strictly above**
   `16790004`, approved original artwork, production Java namespace and
   `com.artcraft.photocraft`. Preserve existing SAF, import fonts,
   updater, GPU diagnostics and ESC/V/T/C/Y/N keyboard behavior.
3. Before accepting an installable candidate, run
   `tools/photocraft_ai_candidate_compatibility.py` against the **public
   reference APK** and the **actual signed candidate**. Require exact
   package, public signing fingerprint, `PhotoCraft` label and launcher,
   approved versionName, and increasing versionCode. Fail closed.
4. Produce a **private review APK only** once the signing identity is
   proven. Back up important documents, install **over** existing
   PhotoCraft without uninstalling it, confirm user data remains intact,
   and retest custom fonts, SAF, update checker, ESC/V/T/C/Y/N, AI
   background removal, consent, cancellation, masks and Undo/Redo.
5. Review third-party U2NetP **weights/training-data commercial terms**
   separately. The Android app currently needs its opt-in localhost
   **Linux Lab** CPU server to be running; this is **not** a standalone
   on-device ONNX-in-APK engine. Do not advertise it as one.
6. Request explicit owner authorization for merge and/or public
   GitHub Release *only after* the above steps are verified.

## Verified private original-signing attempt — 30 October 2026

The owner explicitly authorized preparing an **original-signed private candidate**
for device testing, **not** a public release. The isolated signing workflow is
on `KosmosSG/photocraft-signing-private`, branch
`release/photocraft-ai-pr93-signed-candidate-20261030`:
[`photocraft-ai-pr93-signed-candidate.yml`](https://github.com/KosmosSG/photocraft-signing-private/blob/release/photocraft-ai-pr93-signed-candidate-20261030/.github/workflows/photocraft-ai-pr93-signed-candidate.yml).
It pins the **tested application source** at
`adb9b2d545f870a022f5d6be81c498668d240501`, then separates the
disposable-key ARM64 compilation from the clean, trusted private signing job.
The second job is designed to verify the published baseline, decrypt the
already-existing production signing backup **only on its own runner**, verify
the original certificate, sign `0.14.0-android.2` (versionCode
`16790005`), and upload **only a private testing artifact**. It does not
merge, tag or publish.

**Actual result:** [private signing run #1](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
failed **before a runner or any step was assigned** (build job `runner_id=0`,
`steps=[]`); signing was skipped. An independent
[no-secret private runner probe](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865)
also failed before runner assignment (`runner_id=0`, `steps=[]`).
This is a **GitHub-hosted private-runner/account availability blocker**, not
evidence of an APK compile or signing failure. Billing, quota, policy or
runner availability are possible causes, **none confirmed**. Do not repeatedly
queue heavy builds until a minimal private runner can actually execute.
No production key was accessed and **no original-signed AI APK exists yet**.
The public [ARM64 package proof #5](https://github.com/KosmosSG/artcraft-android/actions/runs/41033840254)
passed and uploaded a JSON identity report **only**; its disposable APK was
deleted, and is not installable over production PhotoCraft.

## U2NetP model rights — upstream evidence and unresolved distribution gate

The U²-Net author's [response in issue #208](https://github.com/xuebinqin/U-2-Net/issues/208)
(25 May 2021) says the repository's released code and models follow its
Apache-2.0 license, but expressly warns that the **training dataset's rights
are not controlled by the author**. The author separately confirms in that
issue that **u2net.pth and u2netp.pth were trained on DUTS**. The later
[request for commercial-use/redistribution clarification, issue #409](https://github.com/xuebinqin/U-2-Net/issues/409),
was still open with no confirmed answer at this review. The
[rembg project](https://github.com/danielgatis/rembg) also warns that model
weight rights must be evaluated separately from the rembg software license.

**Decision:** Keep U2NetP weights **outside the APK, repository, release
assets and installer**. Existing opt-in Linux Lab processing using the
owner's manually obtained local model remains an experimental personal
workflow; do not advertise blanket commercial rights or automate model
distribution. Before any bundled/hosted/commercial distribution, document
the exact ONNX file provenance and cryptographic hash, license/attribution
and NOTICE requirements, DUTS dataset permissions, and whether an additional
rights-holder confirmation is needed. A source-code Apache-2.0 badge alone
is not proof that training-data and redistributed-weight rights are clear.

## Latest read-only verification — 30 October 2026, 20:17 MYT

- PR #93 remained **DRAFT** at source commit `644f22d34ac64a906c5f353d3fe7656ab543ffcd`.
  Hardened `tools/photocraft_ai_reference_signing.py` to require **exactly
  one anchored, valid aapt package/version record** instead of trusting the
  first matching substring. Added fail-closed tests for duplicate, conflicting,
  malformed and misleading package lines. This change affects **read-only
  reference parsing**, not the owner-tested app, model, APK build or signing.
- [Read-only CI run #41054169508](https://github.com/KosmosSG/artcraft-android/actions/runs/41054169508)
  **passed** all steps: offline parser tests, 17 candidate-compatibility
  rejection scenarios, download and inspection of the actual public PhotoCraft
  baseline, and a **metadata-only** signing reference artifact. No APK was
  uploaded, installed, re-signed or released.
- The historical [ARM64 disposable proof run #4 (41032183666)](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666)
  is **completed/failed**, not running. Its concrete failure was
  `AssertionError: Unexpected versionName`; the subsequent
  [run #5 (41033840254)](https://github.com/KosmosSG/artcraft-android/actions/runs/41033840254)
  **passed** with the `0.14.0-android.2` production-package identity and
  uploaded **only a JSON report**, after deleting its throwaway-signed APK.
  Do not mistake run #4 for the latest proof.
- Private signer [run #41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
  and separate no-secret private runner
  [probe #41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865)
  still show **zero steps / no runner assignment**, with no newer runs
  found on the private candidate branch at this check. No production key
  access or original-signed AI candidate occurred. The exact GitHub
  private-runner/account cause is unverified; avoid repeated heavy retries.
- Model weights remain outside Android artifacts. Owner installation/data
  preservation and final publication approval remain outstanding.

## Candidate identity hardening — 30 October 2026, 21:35 MYT

- PR #93 source commit [`980200d`](https://github.com/KosmosSG/artcraft-android/commit/980200d5705d526ab909c54d60587da10150c3f4) strengthens the **read-only** `tools/photocraft_ai_candidate_compatibility.py` gate. Previously, malformed duplicate `package:`, `application-label:` or `launchable-activity:` lines could be ignored if one well-formed record also existed. The gate now counts **all raw identity records**, rejects malformed/ambiguous duplicates, and adds five regression scenarios (22 total). It does not touch the owner-tested Android app, fonts, SAF, AI model, build identity or signing material.
- [CI run #41064512404](https://github.com/KosmosSG/artcraft-android/actions/runs/41064512404) **passed** on that exact source commit. Its job logs show the parser tests passed, **22/22 incompatible-candidate rejection scenarios** passed, and the real public PhotoCraft release identity was verified again. The only uploaded artifact was the 477-byte `PhotoCraft-PR93-Public-Release-Signing-Reference` JSON metadata; **no APK was built, signed, installed or distributed**.
- Historical regular-package ARM64 proof [#5](https://github.com/KosmosSG/artcraft-android/actions/runs/41033840254) remains the latest completed heavy build; it verified the intended regular PhotoCraft package but deleted the disposable-key APK. The private original-signing run [#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414) and no-secret runner probe [#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865) still have **zero runner assignments and zero steps**, and there are no newer runs on the private candidate branch as of this check. No original-signed AI APK exists; the GitHub private-runner/account blocker still requires resolution before signing can be verified.
- Model weights remain excluded from APK/release assets pending redistribution-rights review. Owner must still validate in-place install/data preservation on HONOR MagicPad 4 and explicitly approve any publication.

## Additional APK signer-record validation — 30 October 2026, 22:39 MYT

- On the **actual latest PR93 branch**, commit [`23be34c`](https://github.com/KosmosSG/artcraft-android/commit/23be34cfe03b5ef9da4cd33c24df08e6cf9c5187) strengthened the **read-only** `tools/photocraft_ai_reference_signing.py` parser. Previously a valid first signer could mask an unexpected second signer or malformed certificate SHA-256 record because only recognized signer matches were counted. The parser now checks **all certificate SHA-256 records**, requires complete well-formed signer lines, rejects additional signer numbers even if their certificate matches, and rejects malformed/trailing data. It still accepts legitimate V2/V3 scheme records that identify the same signer.
- Six additional fail-closed signer regression cases cover extra `Signer #2` records, versioned scheme signer #2, truncated SHA-256, trailing garbage, malformed digest punctuation and unknown signer formats. The real published PhotoCraft APK uses `V3.0 Signer: certificate SHA-256 digest` and remains accepted.
- [Read-only CI run #41073508333](https://github.com/KosmosSG/artcraft-android/actions/runs/41073508333) **passed** at that exact source commit: parser self-tests, **22 candidate-compatibility rejection scenarios**, and Android SDK inspection of the actual public PhotoCraft `0.14.0-android.1` release. Its only artifact is the **477-byte JSON public signing-reference report**. No APK was built, uploaded, signed or distributed in this run.
- Historical ARM64 regular-package disposable-signing proof [#5](https://github.com/KosmosSG/artcraft-android/actions/runs/41033840254) remains successful and metadata-only; proof #4 is a completed earlier failure. Private original-signing run [#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414) and no-secret private-runner probe [#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865) still have **no assigned runners or executed steps**. There is no newer successful private run. **No production-signed AI APK exists**. Do not retry heavy signing until private runner execution is restored.
- This source-only validation change does not modify PhotoCraft Android behavior, the owner-tested AI preview, original signing keys, local model weights, icon, keyboard, fonts, SAF or updater. PR #93 remains **DRAFT**; owner in-place device acceptance and separate publication approval are outstanding.

## U2NetP loopback consent-header ambiguity fix — 30 October 2026, 23:14 MYT

- Source-only commit [`f904234c`](https://github.com/KosmosSG/artcraft-android/commit/f904234c706d1190bdb2e0ba44d19f66ce1f7658) fixes a reproducible consent ambiguity in `tools/photocraft_ai_cpu/loopback_u2netp_server.py`. Python's HTTP header `get()` accepts the first of duplicated headers, so a request with contradictory or duplicated `X-PhotoCraft-Image-Consent` or `Content-Type` fields could be accepted. The local-only sidecar now requires **exactly one** `X-PhotoCraft-Image-Consent: yes` and **exactly one** PNG content-type field before reading image data or launching inference. Existing bearer-token, duplicate authorization/length, request-size, single-worker, timeout and no-persistent-storage protections remain unchanged.
- The synthetic localhost HTTP regression suite now covers duplicate affirmative consent, contradictory consent, duplicate PNG MIME and contradictory MIME; all four must fail without starting the mocked inference subprocess. [CI loopback transport run #41078762874](https://github.com/KosmosSG/artcraft-android/actions/runs/41078762874) **passed** on the exact source commit: **8/8 HTTP tests** plus PNG validation and Python compilation. [Standalone CPU safety run #41078762619](https://github.com/KosmosSG/artcraft-android/actions/runs/41078762619) and [production integration review #41078762589](https://github.com/KosmosSG/artcraft-android/actions/runs/41078762589) **also passed** on that commit. All three runs produced **zero artifacts**; no model download, Android APK, keystore access or public release.
- Owner-tested PhotoCraft Android adapter, UI, keyboard, fonts, SAF, updater and original production package were **not modified** by this change. The original-signed private candidate remains blocked: the private signing workflow and independent no-secret runner probe have still never received a GitHub-hosted runner as of this run; no private candidate has been generated or device-tested. No retry was launched. Model-weight redistribution remains excluded pending licensing review, and PR #93 remains **DRAFT**.

## Known blockers

- The generic `build.sh -photocraft` builder creates
  `keys/artcraft-builder.jks` on runners lacking it; that key **does
  not** establish upgrade compatibility.
- The old `build-photocraft-release.yml` has older tag and signer-output
  assumptions and should not be used to publish this AI version without
  separate correction and review.
- Client-side cancellation closes the HTTP transport and discards the
  result, but the Linux Lab CPU process may still complete after cancellation.
- Linux Lab background execution reliability, model rights and
  in-place installation/data preservation need additional testing.

**PR #93 remains DRAFT. No merge, production key modification, automatic
release, Play Store deployment or stable APK publication is authorized.**
