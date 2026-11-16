# VectorCraft v0.24.1-android.16 — selected-group UI performance (ARM64 TEST ONLY)

## Source
Android.16 is branched **directly from the owner-tested Android.14 candidate**, not Android.15. The pinned official VectorCraft upstream remains f4922aa7ac99a4f6d56fc68a83a44945207ec610; Mostafa Android builder remains 52308fbcb26d8d8625f35fc1f048813f8e1e12a8. All earlier Android.12 production features, Android.13 outline complexity safeguards, and Android.14 in-place worker pan pixel shift remain.

## Device observations (not controlled benchmarks)
- Published Android.12 at **144.83%**, selected brochure group, docked Properties panel and no floating Align panel: **24 FPS, render 26.3 ms, UI 39.3 ms**.
- Android.14 at **147.44%**, selected brochure group and same main Properties pane: **20 FPS, render 25.0 ms, UI 46.5 ms**.
- Android.15 at **146.87%**, selected group **with floating Align panel open**: **2 FPS, render 17.8 ms, UI 454.6 ms**.
- Android.15 was not a fair, identical-layout benchmark and is **excluded from Android.16's baseline**. No conclusion about the source of its 454.6 ms UI cost can be established from these screenshots alone.

## Scoped Android.16 behavior
- Selected-group UI overlay complexity (screen visuals only) on Android is capped at **2,048 anchor points** instead of Android.13's 8,000. For groups beyond this limit, the existing accurate selection bounds and key-object bounding rectangle are displayed rather than thousands of path/anchor overlay mesh elements. The actual art, hit testing, object editing, vector data, images and full-quality save/export are unchanged.
- Cache the expensive recursive selection complexity calculation on Android by **document UID + document revision + selected object IDs**, invalidated on document change, undo/edit, or selecting different objects; scrolling/zooming without editing retains the result.
- For a complex selected group, clear previously retained outlines instead of invoking the mesh assembly pass with empty selected-object lists. Normal selections keep all existing marks.
- Desktop behavior, image mips, render worker, full-raster fallback, 8192-pixel device maximum texture, Android.14 pan optimization and original app features are unchanged.

## Strict tests
Python source guards check all touched anchors before any modification. CI then runs existing Android wheel, stability, text, typing and IME suites; the Android.14 pixel-parity Rust suite remains in place. No Android.15 adaptive pan patch is permitted. Any error fails closed before using permanent signing. Only a disposable-signed, separate-application ARM64 APK may be produced, uploaded to GitHub Actions Artifacts; never publish a production release automatically.

## Owner's benchmark checklist
1. Keep published Android.12 and Android.14 installed; Android.16 installs with a separate application ID and temporary key. Back up the Illustrator source file.
2. Open the same **Vista Kepong_Simplified Brochure** Illustrator .ai at artboard 4, **approximately 147% zoom** on Android.12, Android.14 and Android.16 with the **same large group selected** and no floating Align panel. Repeat FPS, render ms and UI ms readings at rest and while panning, in three trials under similar thermals.
3. Compare panning with two fingers and the trackpad (short and long, every direction), pinch zoom, deselect/reselect, and **View → Hide Edges**. Check all object bounds/handles remain reliable. The large group's per-path selection outlines may intentionally be summarized by a box.
4. Confirm no blank seams, missing content or displaced images at rest; text remains selectable/editable in imported .ai; file save/reopen, Ctrl+Z / Ctrl+Shift+Z, ESC, V/T/H, D/S/C, Ctrl+Q relaunch 10x, original cursor/hover and pen-button stylus wheel, and PhotoCraft-style verified in-app updater all still work.
5. Original linked photographs must be present for full-resolution output: the reported "linked pictures show the low-res..." warning is a separate source-link issue, not an excuse to degrade export resolution.

**Release gate:** a successful GitHub build only proves source checks and packaging, not better actual FPS. Compare device results and get explicit owner approval before original signing, publishing, merging or replacing anything.
