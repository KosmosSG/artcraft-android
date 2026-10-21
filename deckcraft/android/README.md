# DeckCraft Android: isolated 0.8.0 candidate (not released)

**State:** draft candidate. No production APK, permanent key, updater, release, device validation, or schedule is authorized by this branch. No other app files or branches are modified.

## Pinned source and implementation
- Official upstream: [storytold/deckcraft v0.8.0](https://github.com/storytold/deckcraft/releases/tag/v0.8.0), latest stable found on 2026-10-22; tag resolves to `22db9261f9d1a214c296fd390173130c45d76d66`. The checked-out source must match this exact hash.
- Android baseline: [MostafaXS1/artcraft-android](https://github.com/MostafaXS1/artcraft-android/tree/ac54d62d9d2d6f663295a4afd8972a7a3e79f9af) at `ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`, checked out into a disposable isolated builder. The active suite's shared `lib/build-common.sh` is not overwritten.
- DeckCraft source licence: `MIT OR Apache-2.0`, with third-party notices in `NOTICE` and `ATTRIBUTION.md`. The ArtCraft marks/logo assets in `docs/brand/` are **not** part of the open-source grant; assess modified-fork branding and notices before public distribution.

## Target and candidate metadata
- HONOR MagicPad 4 running MagicOS 10; `aarch64-linux-android` / `arm64-v8a`.
- Proposed **unverified identity**: `com.artcraft.deckcraft` (reference-builder default). Do not change this once a signed identity is established without an explicit migration review.
- VersionName `0.8.0-android.1`; proposed APK basename `deckcraft-0.8.0-android.1.apk`.
- **Provisional candidate-only** versionCode `100000001`. This is *not* a reservation for public release; inspect every prior signed, installed and published DeckCraft build before reserving a larger final code.
- The upstream version changes only at each official stable release; start Android revision at `android.1` and increment it for Android-specific changes. Keep monotonically increasing versionCode **even across upstream versions**.
- The candidate is built and signed with a freshly generated per-run local key; the workflow deletes keys and APKs, uploads no temporary-key binaries and has no publishing job. Permanent signing is a separate, future gated stage.

## Approved icon from user-supplied file
- Artwork: original uploaded `Glossy Red Glass Dk Icon(1).png`, 1254×1254 RGBA, original SHA-256 `5cf21d43d1854ba97b1a6cd785d62ff43bc82c1e6ccc235847ee4d8b3f1e878b`.
- Lettering: **Dk** (not DesignCraft's **Dc**); solid deep red, liquid-glass lettering, black surround.
- GitHub stores an **optimized 192×192 WebP derivative** of that artwork as `icon/deckcraft-approved-192.webp.b64` (Base64 UTF-8, decoded only in the runner). Expected decoded WebP SHA-256 `abe5ca50dd86c1ecf1ce5916692c0f273bec9187f7ad03fdbb07c989cbf4f6fa`. The original PNG stays outside GitHub.
- The isolated candidate converts WebP to PNG and supplies it with the existing builder's `-appicon` flag; the builder generates launcher resources. CI must verify the **actual APK** contains mipmap and adaptive icon resources, not merely a preview. Inspect Android launcher masks for black wedges and upscale quality. Prefer the full-resolution master for later production resources.

## Existing DeckCraft APIs and assessment (not claims of tablet functionality)

| Area | Inspected evidence and next gate |
| --- | --- |
| Session and editor | DeckCraft `crates/ui-egui/src/lib.rs` exposes `SlideApp`, `Services`, open/save calls and `SlideApp::run`; the reference builder has a DeckCraft-specific `SAF_RECIPES` entry and generated launcher rather than an `adapters/deckcraft` crate. Verify against v0.8.0. |
| File access | Android reference includes `DeckCraftActivity` and asynchronous SAF inbox bridging with request IDs; the suite association registry maps `.deckcraft`, `.pptx`, `.potx` and `.ppsx`. Test open-with/share, cancellation, permission persistence, URI write-back, save-as and export paths. |
| Presentation fidelity | Upstream reads and writes presentations and has slide editing, thumbnails, shapes, media, charts, layout, and animations. Test real PPTX templates and record unsupported transitions, tables, charts, embedded fonts, shape properties, masters, timing and round-trip diffs. Do **not** assert full Microsoft PowerPoint compatibility. |
| PDF and image export | UI includes `export_as` paths for PDF, JPEG, PNG, PPTX and DeckCraft files; test actual Android chooser, file writes, naming, page dimensions, multi-slide behavior and failed export feedback. |
| Fonts | DeckCraft official releases can embed Montserrat under `CRAFT_FONTS_DIR`; the Android builder provides system font fallbacks. Native TTF/OTF import and a shared SAF font-folder registry remain unimplemented/unproven for this candidate, and must have no floating window. |
| Input and tablet | Reference builder has Android IME and mouse/keyboard handling, but composition, custom shortcuts, undo/redo, touch/stylus, pointer hover, trackpad, zoom, portrait/landscape and slide-layout controls require tablet testing. An optional docked Shortcut Pad needs actual engine commands, not invented key mappings. |
| Slideshow, presenter | DeckCraft has a slideshow UI and media support. External displays/presenter mode, Android surface lifecycle, audio, rendering and navigation must be assessed on actual hardware before promising it. |
| Printing | DeckCraft has desktop print/PDF paths, but Android PrintManager integration has not been demonstrated. Test or add a truthful 'not available' state. |
| GPU | Do not imply Vulkan/Adreno acceleration because compilation succeeds. Inspect actual backend and renderer, log capabilities and fallback, and test resilience to device/lifecycle changes. |
| Updates | There is no verified DeckCraft-specific in-app update checker, persistent opt-in startup setting, release metadata, or guarded upstream automation here. These must be added after identity and release gates. |

## Candidate CI and release gates
1. Source tag/commit and builder hashes equal the audited locks; no moving upstream branch, no unreviewed downloaded toolchain, no changes to sister apps.
2. Run isolated candidate, checking manifest package, exact versionName, provisional candidate-only versionCode, ARM64-only shared libraries, Java DEX, actual launcher images, temporary signing certificate and APK SHA-256. **Do not upload an ephemeral-key APK.**
3. Record workflow build result. A green compile does not establish the real IME, SAF, slide fidelity, playback or GPU behavior.
4. Audit existing DeckCraft signing identity, published APKs and tablet-installed certificate/versionCode. If no prior identity exists, propose a dedicated permanent key with encrypted off-repo backup; never reuse any other app's key. Preserve previous signed distributions.
5. Create a separate review of exact pre-sign and post-sign APK payload manifests, digest changes, certificate fingerprint, signature and release provenance. Release only an immutable, permanently signed APK and matching update metadata after gates pass.
6. New stable upstream release detection must be read-only / proposal-only until explicit reviewed enablement. Never auto-merge, change default branches, move tags, overwrite releases, or activate schedules on main from this PR.

**Known blockers:** no proof of the historical DeckCraft signed identity/versionCode, no verified candidate build result at authoring time, no on-tablet validation, and no validated PowerPoint lossless round-trip. The icon is now staged for candidate APK generation, but is not yet verified in a built APK.
