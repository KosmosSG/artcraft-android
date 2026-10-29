# PhotoCraft Android — AI Tools integration (experimental)

Status: **native AI Tools menu source committed, not built or device-verified**. This branch must not be merged or released until an ARM64 device test passes.

## Sources reviewed
- beckettharriman/openfill (Apache-2.0): desktop PhotoCraft + Python/ComfyUI, no Android build.
- kobaltgit/photocraft-companion (MIT): desktop JSON-RPC/ONNX companion, no Android build.

No third-party code, models, or plugin artifacts are vendored by this initial change.

## Scope and safety
- PhotoCraft only. Preserve package name, production key, launcher/top-left icon, fonts, keyboard shortcuts, update checks and SAF handling.
- Add a native **AI Tools** menu above PhotoCraft's existing top menu. All five processing items and backend/plugin settings are **disabled** until implemented; **About AI Tools…** opens a status dialog. This deliberately does not modify upstream Filter menu, which has no supported adapter extension hook. A true **Filter → AI Tools** submenu requires a separately reviewed upstream-compatible integration later.
- Processing must be asynchronous, cancellable and create a **new masked layer** with one undo step; never overwrite the input layer.
- ComfyUI integration is initially an *explicitly configured remote backend*; an Android loopback address refers to the tablet, not the user's Mac.
- No hardcoded cloud endpoint, background upload, telemetry or auto-downloaded model. Show where image pixels will go and require explicit confirmation for LAN processing.
- Treat LAN HTTP as unencrypted: for an initial prototype use a trusted isolated local network, then add transport authentication or TLS via an audited proxy before general release.
- Do not expose a ComfyUI server publicly; prevent SSRF using strict allowlisting and avoid URL redirects.
- Models and licenses must be reviewed individually, especially for commercial projects.
- Never log user image pixels, prompts with sensitive data, auth tokens or model secrets.

## Code artifacts
- `adapters/photocraft/src/ai_tools.rs` defines tool names and a conservative ComfyUI endpoint parser with unit tests.
- `adapters/photocraft/src/ai_menu.rs` contains the native egui menu and informative preview dialog. Processing actions cannot execute.
- `adapters/photocraft/src/lib.rs` calls this menu before upstream PhotoCraft's UI. The adapter's `prepare.sh` copies these Rust files automatically into staged Android sources. No upstream crates, build workflows, signing identities, manifest, or other apps are modified.

**Behavior:** Running an APK built from this branch will show a new top row containing an **AI Tools** menu above the main PhotoCraft bar. Clicking **About AI Tools…** opens an informational dialog. No network connection or image editing happens. This is an interface milestone only, not a functioning AI implementation.

## Remaining implementation checkpoints
1. Compile the Android adapter and confirm the top AI Tools row and About dialog on HONOR MagicPad 4. Confirm no overlap with the existing File/Filter menus or keyboard shortcuts.
2. Add a permission-aware Android backend connection test with a clear success/failure message. Consider a supported native **Filter → AI Tools** extension rather than patching upstream blindly.
3. Export a temporary selection and mask (not whole documents unless explicitly requested), enqueue generation and poll progress off the UI thread.
4. Decode and validate output dimensions and formats; insert as a new layer; verify Undo/Redo.
5. Evaluate ONNX Runtime Android CPU baseline for background removal and 2x upscale; benchmark on HONOR MagicPad 4 before enabling GPU providers.
6. Add tests for cancellation, invalid outputs, large documents, untrusted networks, rotation/lifecycle and existing font/keyboard/updater regressions.
7. Build a **debug-only candidate** and test on-device before any permanent-signing or public-release action.

## Testing
The standalone address-validation tests can be executed with `rustc --test adapters/photocraft/src/ai_tools.rs -o /tmp/photocraft-ai-tests && /tmp/photocraft-ai-tests`. Full menu validation requires compiling the Android adapter against the exact PhotoCraft 0.14.x workspace and egui 0.36, then testing on-device.

GitHub code commits alone do **not** establish that the APK builds, the menu renders, or AI tools function. No APK, release or device test is claimed here.
