# FilmCraft v0.17.0 → Android compatibility candidate (4 November 2026)

## Source & baseline (verified at preparation time)

- Production **unchanged**: `filmcraft-v0.10.0-android.5`, Android package
  `com.artcraft.filmcraft`, versionCode `1000005` (FilmCraft permanent certificate).
- Latest **published** upstream desktop release: `storytold/filmcraft@v0.17.0`,
  annotated Git ref resolves directly to commit
  `eb59ec09daaea519c9c8fffa404a594ae50d00e0`.
  Published 2026-11-03T00:53:23Z. Upstream `main` is newer, but is not the
  pinned stable release and is deliberately excluded from this port.
- Android builder reference stays at
  `MostafaXS1/artcraft-android@ac54d62d9d2d6f663295a4afd8972a7a3e79f9af`.
  Do not merge that builder wholesale or edit original upstream history.
- Development branch: `feature/filmcraft-upstream-v017-android-20261104`.
  This branch starts from the source of android.5 (d8a4dc732b2d57fdc67ca2a986c774456dafef90).
- Test-only version `0.17.0-android.1`, ephemeral code `1700001`.
  This is a provisional local candidate identifier **not a reserved production release**.
  The temporary signer cannot update the installed android.5 application.

## Scope & feature-preservation requirements

The v0.17.0 desktop architecture might have changed; the legacy v0.10.0
FilmCraft Android overlay and native menus are deliberately left unchanged.
The workflow stops rather than silently dropping feature patches if source
anchors are no longer present. Success of a source check, APK build, or
signature verification is **not** proof of device acceptance.

| Existing FilmCraft feature | Minimum v0.17.0 regression check |
| --- | --- |
| Project/media and timeline | Open, scrub, play audio/video, save/reopen, export a real project |
| Autosave + recovery, session restore | Kill/relaunch, restore documents & workspace safely; detect crashes |
| Imported fonts & 4 GiB / 5,000-file recursive scan | SAF TTF/OTF import, nested folder scan, persistence, visible title render |
| Font / updater menus & feedback | File → Import Font, Help → Check for Updates, clear error/progress status |
| GPU | Real renderer/adapter diagnostic; no false GPU claims; graceful CPU fallback |
| Touch | Two-finger scroll, hold-to-right-click, scaling, stylus/trackpad behavior |
| Physical keyboard & IME | T → type → Esc → V, repeat; D/C/S modal stays modal; Ctrl+W, Chinese IME |
| Adaptive launcher and in-app Fc artwork | Exact approved bytes, adaptive mask safe area; no border or clipping |
| Saving duplicate files | `sample (1).ext` rather than `sample.ext (1)`; SAF save/export |
| Permanent update identity | Same app package and original certificate; increasing versionCode |

## Automatic development and hard stop

`.github/workflows/filmcraft-upstream-v017-compat.yml` starts on pushes to
this isolated branch; it pins stable upstream commit and reviewed Android
builder, checks approved artwork, stages exact version overrides in a
disposable runner, attempts to reapply the existing SAF/IME/fonts/update
menus and D/C/S patches, and attempts ARM64 compilation only if guards pass.
The built APK is retained as **EPHEMERAL-NOT-FOR-UPDATE** for inspection;
no release, no private signing secrets, no branch merges.

If an upstream menu, editor, file-system, GPU API, brand resource, Rust/Cargo,
or JNI hook changed, stop with a failing CI check. Adapt each feature behind
a reviewed source-compatible implementation and rerun the tests. Do not
skip or comment out checks to force a green CI result.

The next production candidate must be built and signed with the **existing**
FilmCraft permanent keystore, checked against the installed certificate,
version history, compiled package, versionCode, ARM64 ABI and exact APK
SHA-256. Then obtain owner acceptance on HONOR MagicPad 4 for that
**same signed file**. Explicit owner approval is required to publish any
new GitHub release. Never rewrite android.5 or publish the disposable APK.

## Current evidence

- 2 Nov 2026: upstream stable tag and GitHub release verified.
- 2 Nov 2026: isolated source branch, pinned compatibility workflow,
  fail-closed version staging and offline staging tests committed.
- Native v0.17.0 compile, Android runtime behavior and device testing are
  **not yet verified**. Use the GitHub Actions run/PR checks as authoritative.

## v0.17 compatibility review (4 November 2026)

- v0.17 adds 32 commits beyond v0.16, including timeline playback and export status improvements, safer imports and GPU Bokeh optimizations.
- Open Project now uses the unsaved Save/Don't Save/Cancel prompt. Adapt the temporary Android physical D/C/S bridge for Open as well as Close and Quit; preserve original save guards.
- Reviewed v0.16 source and builder overlays may be reused because upstream egui/winit pins are unchanged, but require actual compilation and device testing.
- Branch derives from the previous v0.16 compatibility branch, itself based on the unchanged published android.5 source. This is NOT a new production baseline.
- Test APK retains the original app ID with a disposable signing key. **Do not replace installed stable FilmCraft with it**; testing should use a separate device/profile or independently verified separate-ID candidate.
- Stop at test APK. No production signing, stable-source merge or release is authorized.
