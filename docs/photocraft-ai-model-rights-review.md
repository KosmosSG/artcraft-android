# PhotoCraft AI — U2NetP model rights and stable-release decision record

**Review started:** 1 November 2026  
**Scope:** PhotoCraft Android AI Tools PR #93, local Linux Lab U2NetP CPU inference, and the public V2-signed experimental preview.  
**Decision:** **Commercial licensing clearance NOT established. Do not represent the AI model, dataset, or model weights as commercially cleared.**

## What is distributed versus what runs locally

The PhotoCraft AI preview APK `photocraft-v0.14.0-android.2-ai-v2-preview` contains the Android UI and loopback client but **does not bundle the U2NetP ONNX weights**. The model remains in the owner's separate Linux Lab environment, is explicitly downloaded by the owner, and runs in a manually started local Python/ONNX CPU sidecar. The APK cannot perform U2NetP background removal without that service and model. A public prerelease has already been published; the presence of the prerelease is **not** a legal clearance or stable-release approval.

The build workflow must continue to fail if a new APK bundles `.onnx`, `.pth`, `.pt`, `.tflite`, `.ort`, `.ckpt`, `.gguf`, `.h5`, `.hdf5`, or `.safetensors` model-weight files.

## Upstream evidence (reviewed 1 November 2026)

| Item | Public evidence | Current conclusion |
| --- | --- | --- |
| U-2-Net project code | [Original U-2-Net GitHub license](https://github.com/xuebinqin/U-2-Net/blob/master/LICENSE), Apache License 2.0 | Code license is Apache-2.0; preserve attribution and any applicable notices. |
| Upstream U2Net/U2NetP checkpoints | [Original maintainer's comments on code/model license and training data](https://github.com/xuebinqin/U-2-Net/issues/208) | Maintainer states released code/models share the project's license, but explicitly does not control the licenses of training datasets. This does **not** settle dataset questions. |
| U2NetP ONNX distribution | [rembg README](https://github.com/danielgatis/rembg) | rembg code license does not automatically grant rights for every separate model weight. Pin source/version and verify hashes; do not infer commercial clearance from a mirror or runtime package license. |
| DUTS training data | [DUTS project page](https://saliencydetection.net/duts/) | Source page reserves rights to original dataset authors and requests attribution; there is no unambiguous commercial reuse permission shown there. The copyright, terms and potential training-data implications require qualified review. |
| Provenance for exact locally cached ONNX weight | PR #93 benchmark's pinned model checksum and rembg release download | Integrity and basic model identity can be checked, but checksum verification is **not** a license grant or proof of dataset rights. |

## Release decisions and guardrails

- **Current decision for the existing public APK:** preserve its experimental **Prerelease / Preview** status and its no-bundled-model architecture; do not silently turn it into a stable/Latest commercial offering.
- **Unresolved before declaring AI production-stable for commercial distribution:** document the exact U2NetP weight origin and conversion chain; obtain clear licensing/provenance guidance where needed (including DUTS/ImageNet-derived training images); decide what use cases are permitted and what notices must accompany distribution; request legal review for commercial deployment.
- **Additional engineering checks:** longer Android foreground/background and Linux Lab suspension/resume tests; cancellation and disconnect behavior; file/Undo/Redo regressions; old-to-V2 signer migration messaging and V2-to-V2 upgrade acceptance. A successful synthetic CI run is not a substitute for real-device lifecycle testing.
- **Signing:** permanent V2 signer certificate `EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936`. The original public PhotoCraft signing certificate differs, so Android cannot update an originally signed app in place. Never rotate the key or describe V2 as a seamless upgrade.
- **Required owner approval:** a distinct approval for a stable/Latest release after recorded rights, device, and release checks. The owner's prior approval to publish a **prerelease** and confirmation of seven on-device features do not themselves establish these further checks.

## Suggested rights-holder inquiry (draft only; NOT sent)

> We are assessing commercial use of U2NetP for a background-removal feature in an Android application. The model inference runs locally in a separate user-managed Linux environment; model weights are not embedded in the APK. Could you clarify the distribution/use terms for the original U2NetP checkpoint and the rembg ONNX conversion, plus any known restrictions or attribution obligations arising from training on DUTS/ImageNet-derived images? We want to accurately describe what permissions are established and which require separate dataset-owner approval.

**Status:** `model_rights_review_pending`. Update this record only with source-backed evidence and reviewer/owner decisions; do not change it to "cleared" based only on a successful model benchmark or device test.
