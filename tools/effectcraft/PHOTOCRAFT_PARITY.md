# EffectCraft Android — PhotoCraft parity specification

Status: **API compatibility confirmed for selected primitives; Android feature wiring NOT yet merged/built**.
Scope: **EffectCraft only**, on the existing draft PR. Do not touch other adapters, certificates,
PhotoCraft releases, main/default branch, or enable GitHub release schedules.

## Reference behavior to preserve

Use the user-tested PhotoCraft `0.10.0-android.2` as a design reference, not a dependency.
PhotoCraft has private TTF/OTF imports, read-only shared SAF font tree selection/refresh,
non-floating UI, in-app GitHub release check, graphics diagnostics, file SAF bridge and
physical keyboard handling. Reuse the UX, not PhotoCraft-specific JNI APIs or text registry.

## EffectCraft API anchors at official `storytold/effectcraft@v0.13.0`

- `crates/text/src/fonts.rs`: `add_font_data(Vec<u8>) -> Vec<FaceId>`,
  `DirectorySource::system()`, `rescan_system()`, and `EFFECTCRAFT_FONT_DIRS`.
  Supports native custom fonts without changing upstream engine behavior.
- `crates/ui-egui/src/lib.rs`: `Hooks::file_dialog_async` and `FileDialog`
  variants for file import/save/project/folder operations; no need for synchronous
  on-frame Android pickers. `EffectcraftApp::new(Session)` is the UI entry point.
- `crates/host/src/lib.rs`: `session()` wires media, expressions, script,
  actual exporter/importer and render queue. **Do not build a UI shell with
  `Session::new()` if that drops those services.**
- `crates/engine/src/shortcuts.rs`: `Keymaps`, `SHORTCUTS_FILE`,
  `Conflict`, editable preset APIs and a read-only default preset; reuse rather
  than imposing Photoshop's defaults on After Effects-style commands.
- `crates/engine/src/session_settings.rs`: settings & keyboard presets can persist
  via the app config store; Android-specific update-check preferences need their own
  durable setting, not an unsaved UI boolean.
- Existing suite builder `lib/build-common.sh`: EffectCraft `SAF_RECIPES` with async
  file dialog, `saf_poll`, document intent, audio hook, and preferences wiring.
  Preserve those and verify generator compatibility before generating an APK.

## User-facing feature requirements and build acceptance

| Feature | Required EffectCraft behavior | Present state |
| --- | --- | --- |
| Import fonts | Menu command **File ▸ Import Fonts…** or logical text/settings location; Android SAF file picker limited to **.ttf/.otf**; reject empty, invalid and >32 MiB files; store durable private copies under `custom-fonts/`; call EffectCraft's font registry and refresh Character font selection without floating font window | API ready; UI/Android integration pending |
| Shared fonts | **Settings/Fonts ▸ Select Shared Font Folder…** points read-only at a user-selected tree such as `Documents/ArtCraft-Fonts`; recurse subfolders (bounded, like PhotoCraft), store persistable read grant, copy selected font bytes to EffectCraft-private cache and register them. Offer **Refresh Shared Fonts** and load last authorized folder on startup; permission expiry must be recoverable | API ready; Java/Rust SAF wiring pending |
| SAF files | Preserve `.ecproj`/media import/open/save/save-as/export and Android ACTION_VIEW/SEND associations. Await async picker without blocking UI; correctly mirror writes to selected URI; test cancellation, provider denial and subsequent refresh | Existing generic builder recipe; not verified in EffectCraft APK |
| Updates | **Help ▸ Check for Updates** read-only, async, from `KosmosSG/artcraft-android` **EffectCraft-only signed releases**; optional startup checks with saved toggle. Distinguish `0.13.0-android.2` from `0.13.0-android.1` correctly, show installed/latest + reason if unavailable. User confirms any visit/download/install. No silent APK installation | Native metadata design; Java/Rust UI pending |
| Update provenance | Only accept approved `effectcraft-v<official-version>-android.<revision>` tags, valid APK assets and verified release/certificate metadata. Exclude PhotoCraft releases, drafts, prereleases, temporary-key builds, filename lookalikes, and bare upstream desktop release tags | Gate required, not complete |
| Shortcuts | Reuse EffectCraft's After Effects-style default keys and `Edit ▸ Keyboard Shortcuts` custom presets/conflict detection. Patch actual Android modifier delivery and IME, not default keymap names. Optional docked touch Shortcut Pad dispatches registered EffectCraft commands, not arbitrary keystrokes | Upstream preset support + builder modifier bridge; device checks pending |
| Tablet | Responsive docked panels/timeline, touch/mouse/wheel, optional stylus pressure/tilt only if input events are real; no invented pen telemetry or compulsory floating controls | Candidate testing pending |
| GPU | Show real renderer/backend, device initialization/error and actual GPU/CPU usage. Never claim Vulkan solely from hardware model; preserve CPU fallback, preview/effects/export and honest diagnostic labels | APIs available; GPU checks pending |
| Icon | Use exact uploaded **Ec** purple liquid-glass art with matching Android mipmap/adaptive resources; compare artwork digest before packing | Artwork prepared outside GitHub; not yet integrated |
| Signing | Ephemeral-key candidate only until existing package/certificate/versionCode checked. No public releases or permanent key changes from this PR | Blocked on signing continuity |

## Implementation order (each is separately verifiable)

1. Introduce EffectCraft-only Android bridge with `effectcraft_text::fonts` and
   persistent private font storage. Test invalid/oversized/duplicate font inputs,
   font restoration at restart, and Character/text animation layout.
2. Add SAF shared tree selection, read grant persistence, bounded recursive scan,
   refresh and UI feedback. Do not require root, broad storage access or Android/data.
3. Add a user-visible, non-floating Check Updates control + saved startup preference.
   Parse only signed EffectCraft Android release metadata; display error/no release/
   latest version without lying. Do not activate unattended auto-build/release.
4. Integrate approved **Ec** resources, implement versionName/versionCode and
   package continuity, build an ARM64 temporary-key candidate on EffectCraft-only
   branch and verify zip payload, DEX, certificate, SHA-256, launcher and ABI.
5. Device-test MagicOS 10: fonts, Montserrat, restart, projects, media imports,
   shortcut hardware modifiers, IME, preview, GPU fallback and actual export.

**None of the pending rows may be presented as a working feature until code,
verified builds and tablet tests justify that claim.**
