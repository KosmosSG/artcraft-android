# PhotoCraft Android — AI Tools integration (experimental)

Status: **AI Tools menu, owner-tested keyboard shortcuts and approved Pc launcher validated on HONOR MagicPad 4 (October 29, 2026); the new Window visibility toggle requires a fresh ARM64 test.** PR #93 remains draft, and AI backends remain disabled.

## Sources reviewed
- beckettharriman/openfill (Apache-2.0): desktop PhotoCraft + Python/ComfyUI, no Android build.
- kobaltgit/photocraft-companion (MIT): desktop JSON-RPC/ONNX companion, no Android build.

No third-party code, models, or plugin artifacts are vendored by this initial change.

## Scope and safety
- PhotoCraft only. Preserve package name, production key, launcher/top-left icon, fonts, keyboard shortcuts, update checks and SAF handling.
- Keep the native **AI Tools** top strip (not a floating palette). Add a checked **Window → Show AI Tools** item to show/hide that strip. It defaults to visible, saves the preference in app-private storage, and the File/Edit/... menu remains accessible while hidden. The dedicated preview workflow inserts the Window command only in its pinned official PhotoCraft v0.14.0 build checkout, after the owner-tested menu port; it does **not** change upstream repositories, other ArtCraft apps, or the production PhotoCraft APK. All five AI processing items and plugin/backend settings remain disabled; **About AI Tools…** remains informational.
- Processing must be asynchronous, cancellable and create a **new masked layer** with one undo step; never overwrite the input layer.
- ComfyUI integration is initially an *explicitly configured remote backend*; an Android loopback address refers to the tablet, not the user's Mac.
- No hardcoded cloud endpoint, background upload, telemetry or auto-downloaded model. Show where image pixels will go and require explicit confirmation for LAN processing.
- Treat LAN HTTP as unencrypted: for an initial prototype use a trusted isolated local network, then add transport authentication or TLS via an audited proxy before general release.
- Do not expose a ComfyUI server publicly; prevent SSRF using strict allowlisting and avoid URL redirects.
- Models and licenses must be reviewed individually, especially for commercial projects.
- Never log user image pixels, prompts with sensitive data, auth tokens or model secrets.

## Code artifacts
- `adapters/photocraft/src/ai_tools.rs` defines tool names and a conservative ComfyUI endpoint parser with unit tests.
- `adapters/photocraft/src/ai_menu.rs` contains the native egui menu, status dialog and app-private visibility persistence. Processing actions cannot execute.
- `tools/photocraft_ai_window_patch.py` adds the Window checkmark and toggle to the existing Android-only menu port inside disposable CI; it checks exact source anchors and refuses drift. `tools/photocraft_ai_preview_stage.py` grafts the current PR93 menu onto the owner-tested keyboard/branding source; `adapters/photocraft/src/lib.rs` documents the standalone menu hook. Production signing and source remain unchanged.

**Expected behavior in the next tested preview APK:** `Window → Show AI Tools` has a checkmark by default. Unchecking removes the separate AI Tools row without affecting the main PhotoCraft menu or physical keyboard shortcuts. Checking restores it; relaunch retains the choice. `AI Tools → About AI Tools…` remains informational. No AI processing, model download, network connection or image upload happens.

## Remaining implementation checkpoints
1. Compile a separate preview ARM64 APK and test **Window → Show AI Tools**: checked initially, hide/reveal correctly, no blank top strip when hidden, relaunch preserves choice, About dialog works. Verify physical Esc, V/T, Ctrl+W C/Y/N, approved Pc launcher/native logo, fonts, SAF and updater remain intact.
2. Add a permission-aware Android backend connection test with a clear success/failure message. Consider a supported native **Filter → AI Tools** extension rather than patching upstream blindly.
3. Export a temporary selection and mask (not whole documents unless explicitly requested), enqueue generation and poll progress off the UI thread.
4. Decode and validate output dimensions and formats; insert as a new layer; verify Undo/Redo.
5. Evaluate ONNX Runtime Android CPU baseline for background removal and 2x upscale; benchmark on HONOR MagicPad 4 before enabling GPU providers.
6. Add tests for cancellation, invalid outputs, large documents, untrusted networks, rotation/lifecycle and existing font/keyboard/updater regressions.
7. Build a **debug-only candidate** and test on-device before any permanent-signing or public-release action.

## Testing
The standalone address-validation tests can be executed with `rustc --test adapters/photocraft/src/ai_tools.rs -o /tmp/photocraft-ai-tests && /tmp/photocraft-ai-tests`. Full menu validation requires compiling the Android adapter against the exact PhotoCraft 0.14.x workspace and egui 0.36, then testing on-device.

An earlier preview APK was successfully built and owner-tested for the AI menu, keyboard and approved icons. **The new Window visibility toggle is not verified until its new ARM64 workflow succeeds and the owner tests it on-device.** No public release, permanent signing, or functional AI backend is claimed.
