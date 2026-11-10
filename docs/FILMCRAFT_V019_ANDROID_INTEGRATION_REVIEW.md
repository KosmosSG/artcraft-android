# FilmCraft v0.19.0 Android selective integration review — 2026-11-10

## Source identity and protection
- Android published baseline: `filmcraft-v0.17.0-android.1`, commit `71f5e39a3cb71ab11c09abb8d4a5e372e5584711`.
- Dedicated branch: `integration/filmcraft-upstream-20261110`, created directly from the published baseline.
- Official upstream: `storytold/filmcraft` tag `v0.19.0`, commit `d1af238bba9fc814487c81e47b53543dff435c09`.
- GitHub comparison `v0.17.0...v0.19.0` reports 299 commits; changes span codec, audio DSP, GPU, UI, export, timelines and Cargo dependencies. GitHub compare file listings may be truncated; do not use a partial list as proof of full coverage.

## Fail-closed port rules
1. Preserve approved launcher artwork, Fc menus, fonts, updater, SAF handling, keyboard/IME/ESC/DCS, adaptive cursor, trackpad hover, Android lifecycle, saved projects and stable package identity.
2. Transfer upstream v0.19 implementation selectively in a disposable upstream checkout. Do not reset this Android branch to desktop source or overwrite the Android overlays.
3. Review `tools/filmcraft/runtime_patch.py`, `native_menu_patch.py`, `header_patch.py`, `patch_unsaved_dcs_v017.py`, `port_android_mouse_winit.py`, and their contract tests against v0.19 exact source anchors. Do not silently bypass failing patches.
4. Port the previously pinned `.github/workflows/filmcraft-upstream-v017-compat.yml` to a **new**, v0.19-only test workflow after compatibility repair. Never change the released v0.17 workflow or production signing pipeline.
5. A **separate-install** disposable APK needs an independent test application ID; merely changing the signing key on `com.artcraft.filmcraft` is not enough to coexist. Preserve production ID only for a future owner-approved permanent update. Update verified test flavor's provider authorities and any hardcoded package references consistently.
6. Verify actual ARM64 ABI, test package ID, disposable certificate, min SDK, version name/code, approved branding, media/SAF intents, overlay linkage and SHA256 before distributing. Validate size reduction without deleting necessary codecs/ABIs/assets.
7. Keep GPU selection and Vulkan/CPU fallback safe. 165 Hz is an adaptive upper bound, not a guaranteed preview decode/display rate; avoid busy rendering, thermal runaway and memory spikes.
8. Do not trigger CI until desktop-source integration and compatibility contract tests are staged. Combine build checks in one run when ready.
9. Stop before production signing, merging, release creation or publication. An APK and successful CI do not constitute MagicPad 4 acceptance.

## Device acceptance checklist
- Five cold launches and ten Ctrl+Q/relaunch cycles; background/resume and rotation without hangs or lost project.
- Load a short H.264/MP4 with audio; play/pause, scrub, seek backwards and check synchronized preview.
- Import several videos and stills via Android SAF; switch clips, trim, split, undo/redo and save/reopen the project.
- Export a short project to SAF and play it in another application; handle codec/unavailable-format failures gracefully.
- Test audio waveform, fades or effects available in this release; confirm no crackle or A/V drift.
- Two-finger timeline and canvas scrolling, pinch zoom, tablet fullscreen; confirm trackpad hover cursor and no accidental selections.
- Type text/titles; ESC exits editing; physical keyboard shortcuts continue after typing; Ctrl+W D/C/S repeatedly.
- Import TTF/OTF, select shared font directory and refresh nested fonts; verify persistence after restart.
- Confirm Fc launcher/menu, appearance/updater, project recovery and no regression in existing MediaStore/SAF permissions.
- Monitor GPU adapter/fallback, frame pacing, power and heat with actual device traces, not inferred FPS.
- Verify temporary package installs alongside stable FilmCraft and cannot overwrite the production package.

## Evidence state
At this review commit: source integration **not complete**; automated regression **not passed**; test APK **not available**; no GitHub Actions run initiated. Preserve those explicit false flags in `configs/upstream/integration-20261110-filmcraft.json` until supported by evidence.
