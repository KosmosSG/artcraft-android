# PhotoCraft Companion → Android: Phase 0 audit and Phase 1 catalog prototype

**Current status: source-only Phase 1 Android prototype.** The Android adapter
contains a read-only SAF plugin picker, bounded .pcpl validation and an egui
catalog UI. The code has NOT been fully Rust type-checked against a complete
upstream PhotoCraft Android build, packaged as an APK, installed, device-tested,
signed or released. It is not an executable plugin manager.

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

## Phase 1 Android implementation (DRAFT PR #109, source only)

- `adapters/photocraft/java/com/artcraft/photocraft/CompanionPluginCatalog.java`
  streams one SAF-provided .pcpl file through bounded ZIP inspection in Java.
  It validates UTF-8 JSON, recursively rejects duplicate JSON keys, unsafe
  paths, nested root conflicts, unsupported types/files, oversized ZIP entries
  and excessive compression. No archive member is extracted or installed;
  remote model URLs are never fetched. Unlike the Python auditor,
  Java ZipInputStream does not expose all UNIX mode metadata, but this is
  non-extracting inspection only.
- `PhotoCraftActivity.java` adds a **separate** ACTION_OPEN_DOCUMENT request
  and reply queue, requesting only a temporary read grant. The document
  open/save queue and URI-to-staged-document mapping remain independent.
  User-selected .pcpl data is inspected directly without writing a staged
  archive to app storage.
- The Java SharedPreferences catalog stores up to 24 sanitized manifest
  summaries (ID, name, version, type and metadata-only status). No model,
  script, source URI, plugin ZIP or executable code is persisted.
- `adapters/photocraft/src/companion_catalog.rs` adds an explicitly
  tap-to-open bottom-right **Plugins · Preview** button and a resizable egui
  catalog window, with 40–44dp touch targets. Import, refresh, cancel and
  rejection statuses are visible, and duplicate/stale picker replies are
  ignored. Each entry is labeled **Not installed · execution disabled**.
- `adapters/photocraft/src/lib.rs` wires the UI into the existing Android
  shell without replacing the editor's input, GPU, font, document or
  staging services. The button is placed behind modal dialogs.
- Source-only CI runs 20 Phase 0 Python regression methods plus 13 Phase 1
  wiring/contract regression methods, Java 17 compilation against Android
  SDK 35 and Rust **syntax parsing** via rustfmt. Those checks are not an
  ARM64 Rust type-check, signed APK acceptance or proof of runtime behavior.

**Device acceptance still required once a safely unsigned ARM candidate is
compiled and owner-original-key signed:** launch and close the catalog,
choose a harmless local .pcpl via Android Documents, confirm metadata appears
after app restart, verify cancel/reject and unknown provider size behavior,
and ensure no command runs, no model downloads, no document modification,
no loss of font import/SAF save/GPU diagnostics/shortcuts, and no modal
dialog bypass or data loss on IN-PLACE upgrade. Do not attempt an original
PhotoCraft upgrade with the incompatible V2 signing certificate.

## Desktop-to-Android compatibility decisions

| PhotoCraft Companion feature | Phase 0 | Planned future gate |
| --- | --- | --- |
| .pcpl packages and manifests | Python audit + Java SAF read-only catalog prototype | Device test, provenance verification and trusted import controls |
| No-code macros | No execution | Strict allowlisted, undoable editor commands |
| Rhai / interactive UI | No execution | Sandbox review; limited widgets and permissions |
| Native AI and remote model URLs | No downloads | Local opt-in U2NetP bridge and weight rights |
| Native algorithm/CLI/dynamic library | No execution | Separate Android security design |
| Floating desktop toolstrip | Small tap-to-open read-only egui catalog | Full touch-ready companion toolstrip pending |
| DirectML and Windows window/tray API | Not portable as-is | Review CPU/NNAPI/Vulkan choices |
| Desktop JSON-RPC port 18492 | Not enabled | Explicit authentication and user consent |
| Plugin marketplace | Disabled | Signed origin, scope and install controls |

## Proposed implementation phases

1. **Phase 0 (source complete):** static compatibility preflight with negative tests.
2. **Phase 1 (source prototype, untested on device):** SAF import for one package;
   display metadata in a disabled plugin catalog. Never execute or extract plugin content.
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

This independent DRAFT PR #109 changes its own Android adapter Java/Rust
sources, tools/tests, docs and source-only CI. Nothing is merged. It does not
touch main, PR #93, other ArtCraft apps, signing workflows, production keys,
APKs or releases. ARM64 compilation, original-key signing on owner HONOR
Linux Lab, tablet acceptance and explicit owner publication approval remain
mandatory before any distribution.
