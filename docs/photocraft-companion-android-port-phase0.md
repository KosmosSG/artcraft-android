# PhotoCraft Companion → Android: Phase 0 read-only package audit

**Current status: pre-port compatibility gate only.** This is not an Android
feature, plugin manager, installer, APK, signed candidate or stable release.

## Upstream reviewed

- Source: https://github.com/kobaltgit/photocraft-companion
- Pinned review commit: 098c8bde3536f6fccba8f5d12b9f882f45ec3354
  (1 November 2026). Upstream source uses the MIT license. When upstream
  implementation is copied in a later phase, retain its license notice.
  The Phase 0 audit is independently implemented; no upstream code,
  branding assets or model weights are copied here.
- Upstream .pcpl packaging uses ZIP archives with plugin.json, optional
  documentation, artwork and Rhai source. Its manifests describe
  no_code, native_ai, native_algorithm and interactive_ui plugins.
  Some manifests list model URLs; these are only metadata and are not
  permission to download or redistribute the models.

## Phase 0 implementation

The tool at tools/photocraft_companion_pcpl_audit.py inspects one local
.pcpl ZIP without extracting it, contacting the network, importing models,
executing commands, reading the Android canvas or writing any files.

Usage:

    python3 tools/photocraft_companion_pcpl_audit.py /path/to/plugin.pcpl

An accepted ZIP reports catalog_status=metadata_only alongside
execution_enabled=false, installed=false, network_used=false and
model_downloaded=false. Even Rhai source is merely examined as bytes.
Success is **not a trusted plugin signature**, a compatibility promise or
authorization to run a plugin.

Archive guards reject duplicate JSON keys, invalid UTF-8, unknown plugin
types, unsafe paths, path traversal, symlinks, special ZIP members, duplicate
members, encrypted/unsupported compression, oversized files, extreme
compression ratios, model weights, executables and malformed manifests.
No marketplace, package installation, model download or auto-update is
included.

Run offline self-tests:

    python3 -m unittest discover -s tools -p test_photocraft_companion_pcpl_audit.py -v

GitHub Actions workflow:
.github/workflows/photocraft-companion-android-pcpl-audit.yml
No APK build, key/secret access, artifact upload or release is permitted.

## Desktop-to-Android compatibility decisions

| PhotoCraft Companion feature | Phase 0 | Planned future gate |
| --- | --- | --- |
| .pcpl packages and manifests | Read-only inspection | SAF picker, consent and metadata catalog |
| No-code macros | No execution | Strict allowlisted, undoable editor commands |
| Rhai / interactive UI | No execution | Sandbox review; limited widgets and permissions |
| Native AI and remote model URLs | No downloads | Local opt-in U2NetP bridge and weight rights |
| Native algorithm/CLI/dynamic library | No execution | Separate Android security design |
| Floating desktop toolstrip | Not ported | Touch-friendly in-app egui overlay |
| DirectML and Windows window/tray API | Not portable as-is | Review CPU/NNAPI/Vulkan choices |
| Desktop JSON-RPC port 18492 | Not enabled | Explicit authentication and user consent |
| Plugin marketplace | Disabled | Signed origin, scope and install controls |

## Proposed implementation phases

1. **Phase 0 (this draft):** static compatibility preflight with negative tests.
2. **Phase 1:** SAF import for one package; display metadata in a disabled
   PhotoCraft plugin catalog. Do not execute or extract plugin content.
3. **Phase 2:** allowlisted no-code command execution with explicit per-action
   user consent, undo transactions, close-dialog and focus regressions.
4. **Phase 3:** touch-focused egui toolstrip; separately reviewed Rhai sandbox.
5. **Phase 4:** optional AI acceleration and model licensing/provenance,
   without bundling unreviewed RMBG, U2NetP, LaMa or upscale weights.

Keep existing PhotoCraft U2NetP PR #93 untouched. Preserve existing ARM64
PhotoCraft package, original production signing certificate, projects,
fonts/SAF, GPU diagnostics, updater, blue Pc icons, keyboard shortcuts and
the 127.0.0.1 bearer-token opt-in model. No default network listeners,
control-port enablement or background AI workers.

This independent draft branch changes only tool/tests/docs and a CI workflow.
It does not touch main, PR #93, other ArtCraft apps, signing workflows,
production keys, APKs or releases. Any Android integration later requires
a separate build, tablet testing and explicit owner release approval.
