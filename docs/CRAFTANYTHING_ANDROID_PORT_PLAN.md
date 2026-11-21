# CraftAnything Android Port — Stage 1 Audit

**Status:** Stage 1 feasibility audit complete; implementation not yet started.  
**Target repository:** `KosmosSG/artcraft-android`  
**Development branch:** `craftanything-android-port`  
**ArtCraft base:** `main` at `839c12acc8ba2a2ef67aa5b18c4c9d16d4882f6b`  
**Upstream project:** `https://github.com/storytold/craft-anything`  
**Upstream baseline:** v0.6.1 tag `48a9c5a60ff83ff620f98661339be6281a7debc6`  
**Audited upstream main head (2026-11-22):** `e64d7cb73d7f39323b7040a984e0f9b3f7981146`

## 1. Decision

Proceed with a **separate CraftAnything Android application**, not a feature merged into PhotoCraft or another existing Craft app. Use a distinct package identity (proposed: `com.artcraft.craftanything`) and isolated build output. Keep all existing production APKs, release tags, permanent signing keys, and approved Android customizations unchanged.

The initial product target is an ARM64 Android tablet APK for the HONOR MagicPad 4. It should expose CraftAnything's Study → Build → Check → Ready workflow with tablet-friendly touch, stylus, physical keyboard, trackpad, file selection, progress, and project controls.

## 2. Upstream architecture and licensing

The upstream workspace is Rust 2024, requires Rust 1.97+, and declares `MIT OR Apache-2.0`. Preserve both license texts, copyright/attribution notices, and upstream NOTICE/attribution material in any redistributed source or APK.

The workspace has three application surfaces:
- `apps/craft-anything`: native eframe/egui desktop application.
- `apps/craft-anything-cli`: command-line and MCP entry point.
- `apps/craft-anything-web`: deliberately reduced WASM file-inspection application; it does not include the full engine, platform, AI or desktop UI.

The reusable core is split across `craft-anything-engine`, `craft-anything-platform`, `craft-anything-ai`, `craft-anything-setup`, `craft-anything-engines`, and `craft-anything-ui-egui`. The desktop entry point constructs `Session`, registers engine/AI/setup tools, creates `Engine` and `AiHub`, then launches `CraftApp`.

## 3. Android compatibility findings

The ArtCraft builder already targets Rust/egui NativeActivity APKs and supports ARM64. It generates a generic launcher only when an upstream app follows the expected public `*App`, `Session::new()`, and `Services::default()` shape; otherwise a maintained adapter under `adapters/<app>/` is required.

CraftAnything does **not** follow that generic constructor shape. Its desktop startup assembles Settings, Session, engine tools, plugins, AI hub and startup jobs. Plan on a dedicated adapter and a deliberate Android startup composition, rather than expecting the generic launcher to work unchanged.

Known platform-sensitive areas from the audited manifests:
- Desktop eframe features include `wayland` and `x11`; the Android target needs an Android-appropriate feature set and NativeActivity/WGPU backend.
- The platform crate owns child processes, pseudo-terminals, process groups and sandbox/engine-store services. These must be audited and selectively enabled for Android; do not assume Android process semantics equal desktop Linux.
- Native file dialogs (`rfd`) and desktop clipboard (`arboard`) need Android SAF and Android clipboard bridges.
- Coding-agent integrations expect local agent CLIs and process execution. Their availability, installation and authentication cannot be assumed on Android.
- Screenshot capture and browser/app inspection capabilities are platform-dependent and must report unavailable capabilities accurately rather than silently pretending they work.

## 4. Recommended runtime split

Use a **tablet APK + optional Linux Lab worker** architecture.

**Android APK responsibilities**
- Native CraftAnything tablet UI and project/session controls.
- Android SAF document/file selection and exports.
- Android clipboard, lifecycle, keyboard, stylus and trackpad handling.
- Pairing, connection status, task progress, cancellation, and clear capability reporting.
- Local read-only/file-analysis features only where the relevant upstream crates are proven Android-compatible.

**Linux Lab worker responsibilities (optional, separately installed/configured)**
- Local coding-agent CLI discovery and execution.
- Long-running build/rebuild processes, pseudo-terminal interaction and process supervision.
- Toolchains and engines that are not practical or supported in Android app sandbox.
- Secure authenticated communication with the APK; do not expose an unauthenticated command-execution endpoint.

The APK must remain useful when no worker is paired: explain which local inspection functions are available and which build/agent actions require a worker. Do not hard-code secrets or copy agent credentials into the APK.

## 5. Required ArtCraft builder integration

The current builder's app allowlist, title mapping, source URL construction, source checkout path, package metadata, workflow matrix and release configuration are app-specific. Add a source override for the hyphenated upstream repository name (`craft-anything`) rather than incorrectly deriving `storytold/craftanything` from the app ID.

Register the new app consistently in:
- `lib/build-common.sh` app allowlist/title/source mapping and isolated output paths.
- A dedicated `adapters/craftanything/` manifest, Rust adapter and Java Android Activity/SAF bridge as needed.
- `configs/release-gates/suite.json` and associated schema/tests/workflows.
- `configs/feature-parity.json` and `tools/suite_feature_parity.py` app registry. These currently enforce exactly 13 existing apps; extend deliberately to 14 rather than weakening the validator or modifying existing app requirements.
- Documentation and test/build workflows, with a unique package ID, versionCode namespace, and disposable test signing.

The suite-wide font/update requirements apply where the app has corresponding text/font features and Help/update navigation. Implement meaningful native behavior and tests; do not add nonfunctional menu items or claim feature parity without exact-APK evidence.

## 6. Staged implementation and acceptance

1. **Stage 1 — audit (this document):** source, license, architecture, repository rules, and Android blockers documented.
2. **Stage 2 — adapter spike:** add the app mapping and a minimal Android launch adapter on this branch; prove ARM64 compilation without changing existing apps.
3. **Stage 3 — Android services:** SAF, clipboard, lifecycle, input, GPU and storage; add capability reporting and tests.
4. **Stage 4 — Linux Lab pairing:** authenticated worker protocol, explicit pairing/revocation, bounded requests, cancellation and safe command approval.
5. **Stage 5 — feature integration:** progressively enable upstream Study/Build/Check/Ready capabilities after per-feature compatibility tests.
6. **Stage 6 — candidate APK:** isolated package, disposable signing, ABI/manifest/signature checks, APK size optimization and device test on HONOR MagicPad 4.
7. **Stage 7 — release review:** only after user device testing and explicit approval; production signing and publishing remain separate authorized actions.

Minimum evidence: Rust/Android compile, ARM64-only APK inspection, launch and lifecycle tests, SAF open/export, offline/worker-disconnected behavior, secure pairing tests, no regressions in existing suite CI, and device verification tied to the candidate APK SHA-256.

## 7. Safety and release boundaries

- Never modify or replace existing production signing keys.
- Use a separate disposable test key and package ID for candidate APKs.
- Never publish, permanently sign, merge to `main`, or change existing releases without explicit user approval.
- Do not modify existing apps' source, adapters, signing configuration, release workflows or published artifacts as part of this port.
- Keep upstream source pinned to a reviewed tag/commit; review subsequent upstream changes before integrating them.
- Treat inspected apps/files as user-authorized targets only; respect CraftAnything's clean-room and consent boundaries.
