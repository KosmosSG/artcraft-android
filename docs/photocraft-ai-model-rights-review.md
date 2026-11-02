# PhotoCraft AI — U2NetP model rights and stable-release decision record

**Review started:** 1 November 2026  
**Scope:** PhotoCraft Android AI Tools PR #93, local Linux Lab U2NetP CPU inference, and the published V2-signed stable core editor with experimental U2NetP, plus the earlier AI preview.  
**Decision:** **Commercial licensing clearance NOT established. Do not represent the AI model, dataset, or model weights as commercially cleared.**

## Current release status — verified 3 November 2026

The owner-approved [PhotoCraft v0.14.0-android.4 stable **core editor**](https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v0.14.0-android.4) was published on **1 November 2026**, with experimental opt-in U2NetP integration and **no model weights bundled**. This is distinct from the earlier AI Preview prerelease. The stable *editor* label is not a claim that U2NetP model/dataset rights are commercially cleared, that AI inference is production-stable, or that DRAFT PR #93 is merged. The owner rejected android.5 on hardware; no newer release is authorized.

## Confirmed intended use — owner statement, 1 November 2026

The project owner clarified: **PhotoCraft is completely free and is being developed for personal, noncommercial development and testing only.** There is no intended paid app, subscription, monetized AI endpoint, commercial hosted processing, or distribution of U2NetP model weights by the PhotoCraft Android project.

**Practical release assessment for this scope:**

1. Personal local experimentation using the already downloaded U2NetP ONNX checkpoint is a materially narrower use than selling model inference or distributing weights. The U²-Net maintainer stated the released code and models follow the repository's Apache-2.0 license; preserve the license and appropriate attribution. The separate rembg code is MIT-licensed.
2. The original maintainer stated both `u2net.pth` and `u2netp.pth` were trained with DUTS. DUTS's public terms do **not** establish an unrestricted license to the original training material. **No separate DUTS training data is downloaded, reused or redistributed by PhotoCraft.** Training-data restrictions are not automatically proven to attach to model outputs or downstream inference, but that legal question is not conclusively settled by the model license statement.
3. The publicly downloadable PhotoCraft APK remains a **distribution of an Android client**, even though the owner's purpose is personal. Do not label all public users, uses, or the full trained model commercially cleared. No trained weight file is embedded in or downloaded by the APK; the user-managed local Linux Lab sidecar is separate.
4. A commercial licensing outreach is **not a prerequisite for continuing the owner's personal/noncommercial testing**. If the project later includes model weights in distributed artifacts, downloads weights automatically, sells AI features, hosts inference for third parties, or promotes unrestricted commercial downstream use, reevaluate permissions and consult qualified counsel where appropriate.
5. Preserve public notices identifying the U²-Net project/paper, Apache-2.0 model-code statement, rembg MIT code license, third-party provenance, and the original/V2 Android-signing migration warning. **No new model weights, training datasets or license files are bundled into the app.**

**Disposition for the clarified current use:** Personal/noncommercial development scope recorded; commercial-rights approval is **not being claimed or sought at present**. The gate for **any future AI production-stable promotion or new public release** remains pending while third-party notice completeness and device/signing safeguards are reviewed; the existing android.4 stable core-editor release is not awaiting re-publication. This is a scoped risk assessment, **not a legal opinion or blanket rights clearance**.

Sources: [U²-Net maintainer — model and training dataset scope](https://github.com/xuebinqin/U-2-Net/issues/208), [original U²-Net project](https://github.com/xuebinqin/U-2-Net), [DUTS original website](https://saliencydetection.net/duts/), [rembg](https://github.com/danielgatis/rembg).

## What is distributed versus what runs locally

The PhotoCraft AI preview APK `photocraft-v0.14.0-android.2-ai-v2-preview` contains the Android UI and loopback client but **does not bundle the U2NetP ONNX weights**. The model remains in the owner's separate Linux Lab environment, is explicitly downloaded by the owner, and runs in a manually started local Python/ONNX CPU sidecar. The APK cannot perform U2NetP background removal without that service and model. An earlier AI Preview prerelease and the owner-approved android.4 stable core editor have been published; neither publication establishes model-rights clearance or approval of any future AI release.

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

- **Current decision for public android.4:** preserve its published **stable core-editor** status and no-bundled-model architecture while explicitly labeling U2NetP **experimental**. The earlier AI Preview remains a historical prerelease. Do not silently market either as commercially cleared or promote a new AI-stable release.
- **Unresolved before declaring AI production-stable for commercial distribution:** document the exact U2NetP weight origin and conversion chain; obtain clear licensing/provenance guidance where needed (including DUTS/ImageNet-derived training images); decide what use cases are permitted and what notices must accompany distribution; request legal review for commercial deployment.
- **Additional engineering checks:** longer Android foreground/background and Linux Lab suspension/resume tests; cancellation and disconnect behavior; file/Undo/Redo regressions; old-to-V2 signer migration messaging and V2-to-V2 upgrade acceptance. A successful synthetic CI run is not a substitute for real-device lifecycle testing.
- **Signing:** permanent V2 signer certificate `EDDA8AB30390E383E10450193B8AE5864312A6FF80E9D6C7F3437816524E6936`. The original public PhotoCraft signing certificate differs, so Android cannot update an originally signed app in place. Never rotate the key or describe V2 as a seamless upgrade.
- **Required owner approval:** a distinct approval for any **future AI production-stable/Latest release** after recorded rights, device, and release checks. The owner's prior approval to publish a **prerelease** and confirmation of seven on-device features do not themselves establish these further checks.

## Suggested rights-holder inquiry (draft only; NOT sent)

> We are assessing commercial use of U2NetP for a background-removal feature in an Android application. The model inference runs locally in a separate user-managed Linux environment; model weights are not embedded in the APK. Could you clarify the distribution/use terms for the original U2NetP checkpoint and the rembg ONNX conversion, plus any known restrictions or attribution obligations arising from training on DUTS/ImageNet-derived images? We want to accurately describe what permissions are established and which require separate dataset-owner approval.

**Status:** `model_rights_review_pending`. Update this record only with source-backed evidence and reviewer/owner decisions; do not change it to "cleared" based only on a successful model benchmark or device test.
