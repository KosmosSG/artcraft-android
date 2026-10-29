# PhotoCraft Android — AI Tools integration (experimental)

Status: **foundation only; not enabled in an APK**. This branch must not be merged or released until an ARM64 device test passes.

## Sources reviewed
- beckettharriman/openfill (Apache-2.0): desktop PhotoCraft + Python/ComfyUI, no Android build.
- kobaltgit/photocraft-companion (MIT): desktop JSON-RPC/ONNX companion, no Android build.

No third-party code, models, or plugin artifacts are vendored by this initial change.

## Scope and safety
- PhotoCraft only. Preserve package name, production key, launcher/top-left icon, fonts, keyboard shortcuts, update checks and SAF handling.
- Add a native **Filter → AI Tools** submenu (no forced floating palette); settings and features remain opt-in.
- Processing must be asynchronous, cancellable and create a **new masked layer** with one undo step; never overwrite the input layer.
- ComfyUI integration is initially an *explicitly configured remote backend*; an Android loopback address refers to the tablet, not the user's Mac.
- No hardcoded cloud endpoint, background upload, telemetry or auto-downloaded model. Show where image pixels will go and require explicit confirmation for LAN processing.
- Treat LAN HTTP as unencrypted: for an initial prototype use a trusted isolated local network, then add transport authentication or TLS via an audited proxy before general release.
- Do not expose a ComfyUI server publicly; prevent SSRF using strict allowlisting and avoid URL redirects.
- Models and licenses must be reviewed individually, especially for commercial projects.
- Never log user image pixels, prompts with sensitive data, auth tokens or model secrets.

## First code artifact
`adapters/photocraft/src/ai_tools.rs` declares tool names and a conservative ComfyUI endpoint parser with unit tests. It is **not yet imported in lib.rs**, so existing builds behave exactly as before.

## Remaining implementation checkpoints
1. Inspect the precise current PhotoCraft UI menu extension APIs and isolate a feature-gated menu insertion (default off).
2. Add a permission-aware Android backend connection test with a clear success/failure message.
3. Export a temporary selection and mask (not whole documents unless explicitly requested), enqueue generation and poll progress off the UI thread.
4. Decode and validate output dimensions and formats; insert as a new layer; verify Undo/Redo.
5. Evaluate ONNX Runtime Android CPU baseline for background removal and 2x upscale; benchmark on HONOR MagicPad 4 before enabling GPU providers.
6. Add tests for cancellation, invalid outputs, large documents, untrusted networks, rotation/lifecycle and existing font/keyboard/updater regressions.
7. Build a **debug-only candidate** and test on-device before any permanent-signing or public-release action.

## Testing
The new standalone source can be checked with `rustc --test adapters/photocraft/src/ai_tools.rs -o /tmp/photocraft-ai-tests && /tmp/photocraft-ai-tests`.
The GitHub change is preparatory and does not establish that the Android APK builds or runs.
