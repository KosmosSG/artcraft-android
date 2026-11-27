# PhotoCraft Android — PxC integration plan

## Scope

Port the useful PxC generation workflows into PhotoCraft's Android-native AI Tools UI. Do not package the PxC desktop GUI, Python runtime, ComfyUI, model weights, or Tkinter dependencies inside the APK. The Android app should be a client for a user-configured ComfyUI server; the model execution remains on that server.

PxC repository: https://github.com/KosmosSG/pxc  
Inspected PxC package version: 1.1.1 (pyproject.toml / pccomfy/__init__.py).  
PxC licence: MIT OR Apache-2.0. Model files and custom nodes keep their own licences.

## Protected baseline and branch

- Approved PhotoCraft Android baseline: `photocraft-v0.23.1-android.5`.
- The companion foundation branch is based directly on the protected release tag commit `36cace94c2fb589cae68a614eef6d8e98a4230c4`.
- This work is isolated on `feature/photocraft-pxc-android-20261127`.
- Do not merge, publish, or use production signing credentials from this branch.
- Keep the original OpenFill branch and published APK unchanged.

## Compatibility gate

PxC's current README documents support for PhotoCraft 0.20.2 through 0.23.1 and explicitly warns that PhotoCraft 0.24 (including release candidates) loses the selection for Fill, Remove, and Edit-with-selection. Keep the first Android PxC port on the 0.23.1 baseline. Any future 0.24+ migration must pass an explicit selection round-trip test before it is considered compatible.

## What the code inspection found

PxC is not an Android library. It is a Python desktop application. Its PhotoCraft client connects to `127.0.0.1:7878`, authenticates with a PhotoCraft control-channel token, and uses JSON-lines RPC methods including `ui.inspect`, `engine.execute`, `app.save`, and `app.open`.

PxC's ComfyUI client uses HTTP endpoints such as `/system_stats`, `/object_info`, `/upload/image`, `/prompt`, `/history/<prompt_id>`, `/view`, `/interrupt`, and `/queue`; WebSocket progress is optional.

The existing Android companion foundation is a different, deliberately restricted protocol on `127.0.0.1:18492`. It supports authenticated inspection and a tiny approved command set. It is not a drop-in PxC control server and must not be advertised as one. Do not expose PxC's full `engine.execute` or file-open/save surface through an unrestricted proxy.

## Android-native feature mapping

| PxC feature | Android port |
| --- | --- |
| Text to Image | ComfyUI API workflow; insert result as a new undoable layer or new document |
| Expand Image | Crop/expanded-canvas workflow; require explicit canvas-state validation |
| Fill | Selection snapshot + mask upload + inpaint workflow; preserve selection and document revision |
| Remove | Selection/mask workflow with explicit prompt/target; insert undoable result |
| Edit canvas / reference edit / sketch / scribble | Stage after image/reference transport and workflow-template support |
| Refine Image | Whole-image workflow; preserve source dimensions and insert a separate layer |
| Upscale | Whole-image workflow; explicit output-size limits and separate result layer |
| Prompt/style presets and model settings | Native Android UI backed by versioned, user-editable workflow presets |
| Queue, cancel, progress | Bounded HTTP polling first; WebSocket progress may follow |

## Required implementation phases

1. **Server connection and inventory:** user-entered ComfyUI URL, explicit private-LAN opt-in, bounded requests, clear connection/model status, no image upload during diagnostics.
2. **Workflow engine:** versioned API-format workflow templates, parameter validation, safe image upload, prompt queueing, bounded history/result download, cancellation and timeout handling.
3. **Undoable document integration:** immutable document snapshot, capture document identity/revision, decode and validate returned PNG pixels, discard stale results, insert one normal PhotoCraft undo step.
4. **Feature rollout:** Text to Image and Upscale first; then Fill, Remove and Expand after selection/mask and crop-state tests; then reference/edit modes.
5. **Device acceptance:** test on HONOR MagicPad 4 ARM64, including large documents, cancel/retry, app background/resume, Wi-Fi loss, server restart, stale-result rejection, Undo/Redo and APK size.

## Current implementation status (2026-11-27)

- ComfyUI endpoint validation and read-only connection/model diagnostics are present in the Android adapter.
- Text to Image is connected to the native AI Tools menu. The worker submits a bounded API-format workflow, polls history, downloads the first output PNG, and fully decodes it before the UI thread inserts a separate undoable layer.
- The result is discarded if the active document identity/revision changed during generation.
- HTTP response handling supports bounded Content-Length and chunked bodies. Unit tests cover workflow structure, prompt limits, path encoding, PNG signature bytes, and response framing.
- The CI test APK uses package `com.artcraft.photocraft.pxc.test`; it is not an update to the published PhotoCraft app.
- Not implemented yet: Fill, Remove Object, Generative Expand, Refine, Upscale, mask/selection upload, WebSocket progress, and cooperative ComfyUI interrupt. These remain disabled in the UI.
- The CI build and on-device ComfyUI round-trip are still validation gates; do not describe this phase as device-tested until those checks pass.

## Security and reliability requirements

- Do not bind an unauthenticated server to `0.0.0.0`; use an explicitly configured private-LAN endpoint and explicit opt-in.
- Never persist bearer tokens or include them in logs, screenshots, crash text, or workflow artifacts.
- Bound image dimensions, request/response bytes, timeouts, polling intervals and concurrent jobs.
- Do not silently overwrite the active document. AI output is a separate layer or document and must be undoable.
- Never apply a result if the source document identity or revision changed while the job ran.
- Do not download or install model weights automatically in the first Android port.
- Treat workflow JSON, model metadata, custom nodes and downloaded outputs as untrusted input.
- Keep diagnostics read-only; only send pixels after a clear per-operation user action.

## Acceptance gate

The branch is not release-ready until the Android workflow can submit a real ComfyUI job, retrieve and fully decode its result, insert it as an undoable PhotoCraft layer, and pass device tests. A successful TCP connection or model inventory is not proof that image generation works.

Build a disposable ARM64 test APK with a separate candidate package and temporary signing identity only. Do not use the production package/signing key, merge to the protected release line, or publish without explicit approval.
