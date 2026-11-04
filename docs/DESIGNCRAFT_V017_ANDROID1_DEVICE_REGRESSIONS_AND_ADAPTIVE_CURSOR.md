# DesignCraft v0.17.0-android.1 — device-test regression gate

**Result: FAIL. Do not publish or permanently sign.**
Protected branch: `integration/designcraft-v017-published-android9-20261104`.
Published stable source: `652f1475ff02fc7c7dc6b1652f2d36404d931838` (`designcraft-v0.12.0-android.9`).
Tested temporary APK: `com.artcraft.designcraft.test`, workflow `41825406580`.
Reported 5 Nov 2026 on HONOR MagicPad 4 with video `SVID_20261104_233658_1.mp4` (66.6 s).

## Owner-reported blocking bugs

1. Physical keyboard tool shortcuts **V / T / H / others intermittently fail**.
2. **Esc sometimes fails** to exit real text editing. Must leave text intact and release BOTH native TextEdit and Android IME focus.
3. **D / S / C intermittently fail** on save/close; preserve modal precedence, modifier rules, and key-up/repeat suppression.
4. Move **Import Font, Select Shared Font Folder, Refresh Fonts, Reload Font Catalog, Check Updates, Startup Check and Android Tools** to a dropdown under the **approved glossy Dc launcher icon at the top-left**. Remove the separate Android Tools strip only when feature parity is verified.
5. Touch and trackpad zoom/scroll broken or stuttering: preserve device-specific touch pinch, trackpad two-finger wheel/pan, cursor position and zoom anchoring. Diagnose rather than multiplying wheel deltas blindly.

## Adaptive cursor upstream reference

[MostafaXS1/artcraft-android v0.2.0](https://github.com/MostafaXS1/artcraft-android/releases/tag/v0.2.0) explicitly lists **Adaptive cursor** independently from **GPU acceleration** and **Adaptive icons**.
Compare fork source against pinned Storytold winit and egui-winit. Potential inspection points:
- `vendor/winit/src/platform_impl/android/mod.rs` (pointer class, hover, mouse wheel, touch)
- `vendor/egui-winit/src/android_activity.rs` (Activity pointer-icon JNI)
- `vendor/egui-winit/src/pointer_icon.rs` (cursor shape mapping)
- DesignCraft's overlay `tools/designcraft/overlay_winit_android_mouse.py`

**Do not blindly copy the fork's vendored event loop:** current overlay already maps mouse hover/wheel/touch, so duplicate events risk the existing scroll/input regressions.

## Acceptance matrix

- V/T/H and all mapped tool shortcuts 10 consecutive times, both after Esc and after menu focus.
- Esc 10 consecutive times while typing, text preserved, tool shortcuts available immediately.
- Ctrl+W followed by D/S/C repeatedly, no inserted letters or false close.
- Icon menu exposes every existing Android action without cropping or duplicate bar.
- Touch pinch zoom anchored between fingers; two-finger trackpad vertical/horizontal scroll; intended zoom gesture anchored at pointer; smooth rendering with no Android navigation gesture mishandling.
- Adaptive cursor follows tool/hover shape and preserves touch vs physical mouse differentiation.
- Font import and 4 GiB/5,000 file recursive scans, updater, permanent signer, package data and current published APK unaffected.
- Only disposable-key ARM64 `com.artcraft.designcraft.test` APK after source checks. No production signing, merge or publication without separate approvals.

**Implementation status:** diagnostic gate recorded; not yet a verified code fix. The previous source-only checks do NOT supersede these real device failures.
