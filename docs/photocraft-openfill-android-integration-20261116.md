# PhotoCraft Android v0.23.1 — OpenFill integration

**Status: Phase 0/1 source work only. NOT an AI feature release, NOT a working Generative Fill APK.**

## Sources and immutable starting point

- User's published stable tag: [photocraft-v0.23.1-android.5](https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v0.23.1-android.5), published 2026-11-13. Work starts on a new branch, leaving the tag, certificate, and existing APK unchanged.
- Third-party source: [beckettharriman/openfill](https://github.com/beckettharriman/openfill), **Apache-2.0** for the OpenFill code.
- OpenFill for desktop PhotoCraft **v0.2.6** supports desktop PhotoCraft **0.12–0.20**, **not Android** or this fork's 0.23.1 editor; a direct ZIP install cannot work.
- OpenFill's local inference path uses **Python/ComfyUI and GPU models**. Its documented Android-compatible approach is not on-device inference: use a **separate GPU computer** running its **paired OpenFill GPU server** over a verified, encrypted Tailscale network, or build a separately consented cloud adapter.
- No third-party models, data, or OpenFill package have been bundled. Model licenses are independent of the code license.

## User-requested integration targets

1. **Fill with a prompt:** selected region and feathered mask → prompt + model → new editable layer.
2. **Remove Object:** selected/painted mask → LaMa or equivalent inpainting → new editable layer; empty/no mask must fail safely.
3. **Generative Expand:** set target canvas ratio or dragged expansion margins → full-resolution outpaint job → new layer and one undoable canvas resize after all data is ready.
4. **Create:** prompt → new document or new raster layer; size/aspect ratio choices.
5. **Remove Background:** inspect and reuse existing experimental U2NetP background-removal path from draft PR #93 where compatible. Never replace a working path with an unverified model, claim it exists in published stable, or ship disputed weights automatically.

UI target: native **Pc → AI Tools** integration with selection-based controls, progress, cancel/discard, model availability and engine configuration. Preserve existing top-left Pc icon, stylus hover and wheel, keyboard shortcuts, trackpad/touch gestures, in-app updater, font library, SAF, production application ID and code signing.

## Phase 1 in this branch: secure connection foundation

- Added an **OpenFill Remote GPU (Preview)** entry to the existing Android AI Tools menu, a **masked pairing-code input**, per-handshake consent, asynchronous authenticated read-only GET **/system_stats**, bounded response/timeouts and a clear status.
- The pairing code is **in RAM only** and is cleared when the dialog closes; it is never written to disk, logged or sent without a user click. No automatic network call at startup.
- Only numeric addresses in **100.64.0.0/10** are accepted, matching a common Tailscale IPv4 endpoint. This is NOT proof that Tailscale is active. The user must confirm VPN connectivity explicitly; an insecure network route remains a risk. Before shipping, verify VPN connection through an Android platform network capability or require an authenticated TLS transport. Do not add unrestricted plain HTTP access to ComfyUI.
- No file, mask, image, prompt or document name is transferred in Phase 1. All editing commands remain deliberately disabled. The connection probe must never be presented as completed AI generation.
- No production workflow, signing secret, tag or APK is changed.

## Work required before a functional test APK

- **Editor snapshot/selection mask:** add read-only capture of visible raster + exact selection/paint mask, with bounds, feathering, DPI dimensions and color-mode conversion. Check source identity and revision before and after each job.
- **OpenFill backend:** investigate OpenFill's existing workflow builder, ComfyUI graph schemas and model catalog for v0.2.6. Port the *job composition* and response handling, not the Python/Tk desktop launcher. Enforce the GPU server's pairing token, allowlisted routes and encrypted route; do not expose raw ComfyUI on the internet. Provide explicit per-image upload consent. Avoid adding a Windows/Linux Python interpreter or gigabytes of models to the Android APK.
- **UI:** implement four modes, prompt history only if opt-in, selection/brush mask, before/after, variations, cancel, model selection and error reporting; use PhotoCraft's touch/trackpad-friendly egui controls. A backend-offline status is not a successful generation.
- **Output:** validate full decoded pixels, dimensions, alpha/masks, colorspace, file sizes and destination document revision; insert into a separate undoable masked raster layer. For Expand, commit the canvas resize as the same undo transaction; never overwrite original pixels, modified documents or the clipboard.
- **Existing Remove Background:** reconcile draft PR #93 U2NetP CPU code against the latest stable; if owner-tested implementation is preserved, show it once rather than two indistinguishable menu commands.
- **Model licenses/rights:** Apache-2.0 covers OpenFill code, not all model weights. For instance FLUX.1 Fill dev and MAT carry non-commercial restrictions; do not auto-bundle them for a commercial-use tool without approval.
- **Device/CI:** require unit tests for parser/security/limits, adapter compile test, Android package+signing verification, 5 cold starts, Ctrl+Q x10, V/T/H/ESC, Undo/Redo, fonts, updater, stylus wheel/hover, touch/trackpad gestures, and all five operations using sample images on HONOR MagicPad 4. Distinguish **source verified**, **APK artifact verified**, **device verified**.
- Create a distinct, *disposable-signed* ARM64 **test** package and use a lightweight Actions workflow until the integration compiles. Never auto-merge, permanently sign, publish or replace PhotoCraft v0.23.1-android.5 without specific approval.

## Current pass/fail statement

- **Phase 1 connector source:** staged for compile/unit validation; it is *not yet tested on a tablet*.
- **AI generation/removal/expansion/create:** **not implemented by this branch yet**.
- **Remove Background:** owner-tested in the earlier separate PR #93 preview; compatibility with published v0.23.1-android.5 has not yet been verified.


## High-resolution prototype (2026-11-16)

The owner-tested <=4 MP Linux Lab U2NetP + new layer + Ctrl+Z path is retained. This branch now tests an experimental <=20MP full-resolution output route: the CPU model processes an RGB proxy capped at a 1536-pixel long edge, then upsamples only its transparency mask and multiplies any existing alpha against original full-resolution RGB pixels. Neither the document dimensions nor its RGB values are resampled. The 4167 x 4167 owner image is under the new 20MP limit. Input PNGs stay bounded to 64MiB, results to 96MiB; Python and Rust validators remain mandatory. Large masks can lose hair/edge detail compared to true full-resolution inference. This is not a device-tested feature yet. Already-installed Linux Lab sidecar helpers must be explicitly refreshed after verification; the launcher does not update automatically. No models are bundled or downloaded.

## Remove Object LaMa readiness

The bundled read-only Linux Lab readiness helper only checks for a verified 205669692-byte LaMa checkpoint (SHA-256 344c77bbcb158f17dd143070d1e789f38a66c04202311ae3a258ef66667a9ea9) under ComfyUI/models/inpaint and the existing comfyui-inpaint-nodes folder. Nothing is installed, downloaded or executed. The Remove Object menu remains disabled until inpainting nodes, model licensing, masked selection export and full Undo-safe layer insertion have been verified on-device.
