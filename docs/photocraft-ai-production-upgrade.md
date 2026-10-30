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
