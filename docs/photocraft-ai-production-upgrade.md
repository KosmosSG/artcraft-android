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

## Linux Lab unsigned APK signing-input proof — 31 October 2026, 00:44 MYT

- Owner requested a PhotoCraft AI `0.14.0-android.2` ARM64 APK for **local signing** on Linux Lab, not an installable APK, merge or publication. [Build run #41086392166](https://github.com/KosmosSG/artcraft-android/actions/runs/41086392166), PR93 commit [`2303e072`](https://github.com/KosmosSG/artcraft-android/commit/2303e0722d799751c1fc08dc7a808c10f0cf9c2c), **succeeded**. All steps passed and artifact [#12992188787](https://github.com/KosmosSG/artcraft-android/actions/runs/41086392166/artifacts/12992188787) (31,367,500-byte compressed ZIP) contained only an **unsigned, non-installable** ARM64 APK, SHA256SUMS and identity reports. The original disposable-key signed APK and temporary key were deleted on the runner; no production key used. The regular PhotoCraft package `com.artcraft.photocraft`, name/launcher, ARM64 ABI, `0.14.0-android.2` / `16790005` were verified. This is **not** an original-signed candidate and cannot update the installed app.
- The successful build's `aapt` logs exposed repeated **ZIP header mismatch warnings** during unsigned archive verification (the source conversion had used forced ZIP64 for individual entries). Rather than distribute that potentially problematic input for local signing, a separate **lightweight, no-ARM-rebuild** regression/normalization workflow was added in [`c57ab5b`](https://github.com/KosmosSG/artcraft-android/commit/c57ab5b43015c9079f664cc01e2e03a66e34b554). It downloaded the exact existing artifact, checked the SHA/provenance, reconstructed ZIP local/central records without forced ZIP64, preserved all member names/order/CRCs/sizes, aligned the output, and asserted `apksigner verify` **rejects** it as unsigned.
- [Signability proof run #41092549070](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070) **passed**: the cleaned APK produced **no ZIP header mismatch warnings** under `aapt`, retained the correct package/version/launcher, and could be signed and verified using a newly generated **disposable test key**. That test-signed APK and test key were **deleted** and were **never uploaded**. Only the clean **UNSIGNED** signing input and JSON/SHA evidence were uploaded as artifact [#12994487844](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070/artifacts/12994487844), named `PhotoCraft-AI-v0.14.0-android.2-CLEAN-UNSIGNED-LINUX-LAB-PR93` (31,366,770-byte compressed ZIP, seven-day retention). **Use this clean artifact rather than the earlier ZIP** for any owner-approved local signing.
- Signing remains an **owner-local step** requiring independently verified access to the **original** permanent PhotoCraft signing certificate SHA256 `45933a886c258e5be9f98ba68dc37e5ee2dd543a6efde008e407879bc9dc59ef`. After signing, run `tools/photocraft_ai_candidate_compatibility.py` against the published `photocraft-v0.14.0-android.1` APK; then back up data and obtain explicit HONOR MagicPad 4 **in-place update** acceptance. A disposable-signed test APK **must never** be installed or distributed. No original-signed PhotoCraft AI APK exists yet; the private Actions signer runner is still unavailable (last observed private runs [#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414) and [#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865) failed without assigned runners). AI model weights remain excluded pending redistribution-rights review.
- This work did **not** modify the owner-tested Android behavior, Linux Lab CPU sidecar, production signing secrets, any other ArtCraft app, main branch or public releases. **PR93 remains DRAFT** and final publication still requires the owner's separate explicit approval.

## Signed-candidate ARM64 ZIP/weight safety gate — 31 October 2026, 00:55 MYT

- The current [PR #93](https://github.com/KosmosSG/artcraft-android/pull/93) remains **DRAFT**. The [clean unsigned Linux Lab input](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070/artifacts/12994487844) is verified but is **not installable**. Its GitHub Actions ZIP upload SHA256 is `b8b55b4ad93630458af14f69d74652a600eb1452ebc32fb54cf82a80911d113e`; the artifact contains its own `SHA256SUMS.txt` for the inner unsigned APK. Artifact retention ends approximately **6 November 2026, 16:44 UTC**. No original-signed candidate is known.
- Commit [`1da1ce0a`](https://github.com/KosmosSG/artcraft-android/commit/1da1ce0a19073d983ca47ce859e1fab876447cc1) strengthens the **read-only, post-signing** `tools/photocraft_ai_candidate_compatibility.py` gate. In addition to existing original-certificate, package, versionCode, name and launcher checks, a future signed APK must now pass ZIP member integrity (CRC), unambiguous entries, safe archive paths, no symlink/encrypted entries, a manifest, **ARM64 native libraries only**, and no accidentally embedded keystore or model weights (`.jks`, `.p12`, `.keystore`, `.onnx`, `.pth`, `.pt`, `.safetensors`). These checks operate on the actual signed APK, **never on signing keys**. Eleven synthetic rejection scenarios were added; the existing 22 compatibility rejection scenarios remain.
- [Read-only CI run #41094124391](https://github.com/KosmosSG/artcraft-android/actions/runs/41094124391) **passed** at that exact commit. Job logs explicitly show `PASS: ARM64 archive and no-embedded-model/key checks (11 rejection scenarios)`, `PASS: production upgrade compatibility gates (22 rejection scenarios)`, and the original published PhotoCraft signer certificate verified from the public release. Its only artifact is a **477-byte signing-reference JSON** [#12995820909](https://github.com/KosmosSG/artcraft-android/actions/runs/41094124391/artifacts/12995820909); **no APK was built or signed in this check**. The latest ARM64 build remains [#41086392166](https://github.com/KosmosSG/artcraft-android/actions/runs/41086392166), followed by the no-rebuild clean unsigned proof [#41092549070](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070).
- Preliminary licensing provenance: the [original U-2-Net project](https://github.com/xuebinqin/U-2-Net/blob/master/LICENSE) displays **Apache-2.0** for its repository, while [rembg](https://github.com/danielgatis/rembg) is **MIT** licensed. This does **not independently establish the precise redistribution rights for the exact cached `u2netp.onnx` weight bytes** or third-party data provenance; do not bundle or redistribute those weights until that provenance/notice obligation is reviewed. The current Linux Lab sidecar retains locally cached weights and no weights are in the APK.
- The private signing run [#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414) and independent private no-secret probe [#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865) remain the latest private runs, both failed **without executing steps or obtaining a runner**. No retry was started. Owner-local original-key signing and the on-device in-place update/data-preservation test remain required before any release decision. No merge, main edit, production key access, install or publication occurred.


## CPU subprocess output-memory guard — 31 October 2026, 02:08 MYT

- At PR93 commit [`fc2b4db2`](https://github.com/KosmosSG/artcraft-android/commit/fc2b4db2ce49c272e087d4bd68505a82a8cc1875), the localhost U2NetP HTTP server and its file bridge stopped using Python `subprocess.run(capture_output=True)` for the CPU inference chain. Previously, child-process stdout/stderr were buffered without a byte limit, despite never being used in the PNG response or for success checks. A verbose or malfunctioning child could therefore exhaust Linux Lab memory during an otherwise bounded image request. Both layers now route child stdout/stderr to `subprocess.DEVNULL`, retain the existing 180-second timeouts, return-code checks, output-file validation and private error responses, and never expose model paths or image data through HTTP.
- Two regression assertions verify that the HTTP transport and file bridge both invoke their mocked inference children with `stdout=DEVNULL`, `stderr=DEVNULL` and without `capture_output`. These are **source/CPU sidecar-only** changes; no model is downloaded, weights bundled, APK compiled, key accessed, device modified or public release created. The owner-tested PhotoCraft Android UI, keyboard, fonts, SAF and updater are unchanged.
- The relevant GitHub Actions checks were automatically queued on that exact commit: [loopback transport #41104333397](https://github.com/KosmosSG/artcraft-android/actions/runs/41104333397), [sidecar integration #41104333475](https://github.com/KosmosSG/artcraft-android/actions/runs/41104333475), [standalone CPU safety #41104333340](https://github.com/KosmosSG/artcraft-android/actions/runs/41104333340), and [production source review #41104333313](https://github.com/KosmosSG/artcraft-android/actions/runs/41104333313). **Results pending at commit time; do not call them passing until checked.** No additional heavy ARM64 build was queued.
- Production-signed candidate remains blocked on original-key signing (private hosted-runner execution unverified; owner-local original-key signing remains an option), followed by the signed APK compatibility gate, HONOR MagicPad 4 in-place/data-preservation test, and separate final publication approval. Keep PR93 **DRAFT** and the clean unsigned artifact private to the owner's local signing workflow.


## 31 October 2026 — historical public failure-artifact leak (manual deletion required)

**Safety finding, not a production-signing breach.** Retrospective inspection of
[failed ARM proof run #41032183666](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666)
found that the approved-branding verifier copied a disposable-key-signed APK
bearing the **regular PhotoCraft package name** into the icon-verification
directory. The old failure-only artifact step uploaded that directory
along with build logs. GitHub reports an unexpired public artifact
[PhotoCraft-AI-PR93-Keyboard-Icon-Failure, ID 12966638625](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666/artifacts/12966638625),
31,308,102 bytes, created 30 October 2026 09:27 UTC and scheduled to expire
6 November 2026 09:27 UTC. Its ~31 MB size, the explicit APK copy in
the verifier, and the upload log are strong evidence that the diagnostic
ZIP contains the throwaway-signed APK. **The ZIP entries have not been
independently extracted/verified**, so do not assert its precise filename
or version. This APK cannot update the original production app because
its signer differs, but it must **not** be presented as a valid test/release
APK. No evidence that the original permanent signing key was exposed.

**Owner action required:** manually delete artifact **12966638625** from the
linked Actions run's artifact controls as soon as possible; the available
GitHub connector has no artifact-deletion action. Do not download, install,
share or re-sign this failed-run diagnostic ZIP. A successful metadata-only
[proof #41033840254](https://github.com/KosmosSG/artcraft-android/actions/runs/41033840254)
and the separately verified **unsigned** Linux Lab input remain distinct.

**Prevention committed to PR93 only:** metadata-only workflow commit
[285ba2c](https://github.com/KosmosSG/artcraft-android/commit/285ba2c878405865f2378bab1b17dbedb581018d)
and unsigned workflow commit
[ee0310a](https://github.com/KosmosSG/artcraft-android/commit/ee0310ab9b3a3d6858b7f7c022f612edc7549b13)
remove failure-diagnostics artifact uploads altogether and always delete the
icon-verification copy and disposable key/output APK. Both were committed
with [skip ci] to avoid two unnecessary expensive ARM64 rebuilds. New
static artifact allowlist regression
[test_public_artifact_safety.py](https://github.com/KosmosSG/artcraft-android/blob/feature/photocraft-android-ai-tools-20261029/tools/photocraft_ai_cpu/test_public_artifact_safety.py)
runs in [CI #41110533672](https://github.com/KosmosSG/artcraft-android/actions/runs/41110533672),
**passed 2/2 tests**, with **no APK build, signing or artifact upload**.
The tests assert that the regular-package proof uploads JSON only, the
Linux Lab workflow uploads only its explicitly named unsigned APK/metadata,
and neither uploads diagnostics or leaves the disposable APK copy.

The earlier run #41032183666 failed on **Unexpected versionName**, not on
an ARM compiler error; later proof #41033840254 fixed the versionName and
succeeded. The separate private signer remains blocked by no-runner
[run #41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
and [probe #41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865).
Do not rerun private signing until a runner is demonstrably available.
PR93 remains DRAFT, with no production-signed AI candidate, no publication
approval and no owner in-place device acceptance.

## 31 October 2026 — bounded localhost HTTP headers before authentication (PR93 only)

**Reproducible source-level risk:** `ThreadingHTTPServer` originally applied the
15-second `REQUEST_READ_TIMEOUT` only **after** the HTTP request headers had
been fully parsed and after bearer-token/consent checks. A local process that
opened a TCP connection and stalled mid-header could leave an idle handler
thread waiting indefinitely, without ever entering the protected PNG upload
path. This is a localhost availability issue, not evidence of remote access.

**Fix:** commit [`00eab900`](https://github.com/KosmosSG/artcraft-android/commit/00eab9007787643c2f04cab73bbabc192f9fa7d1)
introduces `LoopbackHTTPServer(ThreadingHTTPServer)` and applies the existing
15-second socket timeout immediately upon accepting the connection, **before**
request headers are parsed. It still binds only to `127.0.0.1` and retains
the per-image consent, bearer-token checks, 4 MP PNG cap, single-inference
lock, 180-second child timeout, no image persistence and bounded response.
Commit [`184213db`](https://github.com/KosmosSG/artcraft-android/commit/184213db7de414f8dd39a8d42a07785f0daafe65)
adds a live localhost regression: a client sends incomplete authorization
headers, the socket is closed after the short test timeout, and a subsequent
properly authorized PNG request still succeeds.

**CI evidence:** [loopback transport #41118109005](https://github.com/KosmosSG/artcraft-android/actions/runs/41118109005)
**PASS**, and [CPU standalone safety #41118108781](https://github.com/KosmosSG/artcraft-android/actions/runs/41118108781)
**PASS**. The source review initially **failed** on
[#41118108800](https://github.com/KosmosSG/artcraft-android/actions/runs/41118108800)
because its static guard expected the old `ThreadingHTTPServer` constructor
literal; no production identity or transport regression was observed. Commit
[`c47b4e38`](https://github.com/KosmosSG/artcraft-android/commit/c47b4e38112051a628d07809be802701e9639269)
updates the guard to require the **new loopback-only subclass and both
pre-auth header and body timeouts**. [Source review #41118146659](https://github.com/KosmosSG/artcraft-android/actions/runs/41118146659)
**PASS**. No model or image was downloaded; no ARM APK built, key used,
private signing workflow retried, merge, device installation or release.

**Unchanged release blockers:** private hosted signing jobs
[#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
and no-secret runner probe
[#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865)
still failed without an assigned runner; no original-signed AI candidate exists.
Historical failed-build diagnostic artifact
[#12966638625](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666/artifacts/12966638625)
still exists as of this check and needs owner deletion from GitHub UI; it may
contain a disposable-key APK. Owner device acceptance, licensing review and
explicit final publication approval remain required. PR93 stays **DRAFT**.

## 31 October 2026 — absolute upload deadline against slow-trickle clients (PR93 only)

**Reproducible availability risk:** after the pre-auth header timeout fix,
the sidecar still used a single `rfile.read(Content-Length)` with a
15-second **socket inactivity timeout** while holding the one-inference lock.
A localhost client could send one body byte every few seconds, indefinitely
resetting that timeout without completing its PNG. This was an availability
issue within the opt-in `127.0.0.1` endpoint, not a remote bind or a model
data leak.

**Fix and tests:** [`5c78d4d`](https://github.com/KosmosSG/artcraft-android/commit/5c78d4d78ffdd11ba509feec5d1cc59bb7611eaa)
enforces an **absolute monotonic 15-second total body-upload deadline**
with bounded `read1` chunks, independently of how frequently bytes arrive.
The existing token, per-image consent, 24 MiB input/4 MP pixel caps,
single-inference lock, bounded output, private errors and local-only bind
remain unchanged. [`77eb23a`](https://github.com/KosmosSG/artcraft-android/commit/77eb23a846d81f1feb597253fb7cd4fcd310fed8)
adds a live synthetic localhost test that deliberately trickles body bytes
every 40 ms and verifies HTTP 408, **no inference**, lock release and a
subsequent authorized request; [`13097f6`](https://github.com/KosmosSG/artcraft-android/commit/13097f62f3d6e2759781bb1155bb6d678b46da3c)
simplifies the test's wire framing. [`044dfeb`](https://github.com/KosmosSG/artcraft-android/commit/044dfebbbf31e52d7b913266e16171a48013e8cc)
adds an explicit absolute-deadline requirement to the production source
review so this protection cannot be silently removed.

**Verified GitHub Actions:** [loopback transport #41133031167](https://github.com/KosmosSG/artcraft-android/actions/runs/41133031167)
**PASS 10/10**, including the slow-trickle regression;
[production source review #41133031070](https://github.com/KosmosSG/artcraft-android/actions/runs/41133031070)
**PASS**; [standalone CPU safety #41133031057](https://github.com/KosmosSG/artcraft-android/actions/runs/41133031057)
**PASS**. These are source/localhost mocked-inference checks only, **not**
a new ARM APK build or HONOR MagicPad 4 acceptance.

**Release boundaries rechecked:** [historical failed proof #41032183666](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666)
remains completed/failed; [diagnostic artifact #12966638625](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666/artifacts/12966638625)
still exists and requires owner deletion (suspected disposable-key APK).
The [clean unsigned Linux Lab artifact #12994487844](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070/artifacts/12994487844)
remains a **non-installable signing input**, not a production-signed APK.
Private signer [#41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
and no-secrets probe [#41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865)
still show failed/no-runner execution, with **no newer private runs** as
of this check. No signing attempt, secret access, model distribution,
heavy build, merge, device update or public release occurred. PR93 remains
**DRAFT**; original-signed candidate verification, owner in-place tests,
licensing review and separate final publication approval are still required.

## 31 October 2026 — absolute pre-auth header deadline and quiet disconnects (PR93 only)

**New reproducible gap:** The earlier pre-auth socket timeout was an
*inactivity* limit. A localhost client could send one incomplete HTTP header
byte every few seconds, indefinitely resetting that limit and retaining a
handler thread without presenting a bearer token. This is a local
availability concern; the server still binds exclusively to `127.0.0.1`.

**Fix:** [`a9dfa966`](https://github.com/KosmosSG/artcraft-android/commit/a9dfa96696769d4487f8a425ae18ff7f7bc6f13c)
starts a 15-second **absolute header timer** before the HTTP request line is
read, shuts down the socket if headers are still incomplete, and cancels the
timer immediately after header parsing. It does **not** cut off legitimate
CPU inference after valid headers. [`5e99af1d`](https://github.com/KosmosSG/artcraft-android/commit/5e99af1d17dffe88e2fd03d8e44340fc883a9ddb)
adds live mocked-inference tests for slow-trickle authorization headers and
for valid requests whose inference exceeds the shortened test header deadline.
[`26581bc6`](https://github.com/KosmosSG/artcraft-android/commit/26581bc6b94ae9a4f755d40f82e6f3fb993a3fd4)
requires the absolute timer in the production source guard.

**Log-safety follow-up:** Initial passing loopback tests
[#41134782717](https://github.com/KosmosSG/artcraft-android/actions/runs/41134782717)
showed expected `BrokenPipeError` tracebacks when the HTTP parser attempted
to answer a socket intentionally closed by the timer. No bearer token or
image bytes were printed, but these noisy exception traces are undesirable.
[`7e60cb64`](https://github.com/KosmosSG/artcraft-android/commit/7e60cb645dd14634d37fec1beae0e145cb435be6)
now handles **only** expected broken-pipe/connection-reset errors caused by
the expired header timer; unrelated errors still surface normally.
[`7a308375`](https://github.com/KosmosSG/artcraft-android/commit/7a3083752156a8ef4d50c9e1b1d5cc9634c905de)
adds a regression requiring no unhandled server exception on that expected
disconnect. [`d73d4be9`](https://github.com/KosmosSG/artcraft-android/commit/d73d4be9de81a38383504c6865bcb96cf05ceaea)
extends the source guard.

**Verified GitHub Actions:** [loopback transport #41134899566](https://github.com/KosmosSG/artcraft-android/actions/runs/41134899566)
**PASS 13/13** live localhost synthetic-PNG tests, with no
`Traceback`/`BrokenPipeError` in the final job log;
[production review #41134912532](https://github.com/KosmosSG/artcraft-android/actions/runs/41134912532)
**PASS** at the latest code-guard commit;
[CPU standalone safety #41134899627](https://github.com/KosmosSG/artcraft-android/actions/runs/41134899627)
**PASS**. These are source/CPU-sidecar tests only, **not** a new ARM64
APK build, original signing or owner device acceptance.

**Release gates remain:** Historical failed proof
[#41032183666](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666)
is completed/failed, and its [diagnostic artifact #12966638625](https://github.com/KosmosSG/artcraft-android/actions/runs/41032183666/artifacts/12966638625)
was still present at this check; owner deletion remains necessary because
it may contain a disposable-signed APK. The
[clean unsigned Linux Lab input #12994487844](https://github.com/KosmosSG/artcraft-android/actions/runs/41092549070/artifacts/12994487844)
remains **non-installable**. No new private signing runs followed
[failed no-runner signer #41036796414](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41036796414)
or [no-secret probe #41037016865](https://github.com/KosmosSG/photocraft-signing-private/actions/runs/41037016865).
No original-signed AI candidate, in-place tablet acceptance or model-rights
clearance exists yet. No heavy build, signing retry, private key access,
model distribution, merge, device change or publication occurred. PR93 stays
**DRAFT** pending separate owner approval.
