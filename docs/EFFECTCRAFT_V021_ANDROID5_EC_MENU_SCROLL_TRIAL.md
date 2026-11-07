# EffectCraft v0.21.0-android.5 — Ec appearance & trackpad menu trial

Owner-authorized changes (8 November 2026): **EffectCraft only**, no permanent signing or publication.

## Protected source

Start at exact owner-device-tested Android.4 commit `f8ada463e0e37fb591da1b9889f7f30c10c40f16` and keep that ref, published stable release, original package, project data and production signing keys unchanged. Branch: `feature/effectcraft-v021-android5-menu-appearance-scroll-20261108`.

## Changes

- The existing top-left **Ec** brand popup gains **Appearance → System / Light / Dark**. Options persist via EffectCraft's own `appearance.appearanceMode` preference and `apply_prefs`, without replacing settings, theme choices or shortcuts.
- The popup contents live in a bounded, standard egui vertical ScrollArea so hover-wheel/two-finger trackpad scroll is consumed by the open menu.
- The isolated v0.21 Android winit pointer adapter forwards nonzero `MotionAction::Scroll` axes even if Android labels the source generically (instead of Source::Touchpad/Mouse). The existing wheel delta conversion, mouse input, physical keyboard, two-finger canvas gestures, stylus and touch paths remain unchanged.
- One separate `com.artcraft.effectcraft.v021test5` ARM64 APK, temporary disposable signing, GitHub Actions artifact only. Source and CI checks cannot prove HONOR MagicPad behavior.

## Device acceptance

1. With Ec popup open, two-finger trackpad scroll vertically, reverse direction and pause. Verify hovering over a row doesn't activate it or select the canvas.
2. With standard File/Window/Help menus and long submenus, scroll with two-finger trackpad; compare with touchscreen scrolling and physical mouse wheel if available.
3. Ec → Appearance → Light, Dark, System. Verify colors, menu contrast and persistence after quit/relaunch; System follows OS appearance when supported. Check the existing header appearance control still works.
4. Recheck approved Android.4: Ctrl+Q 10x quit/relaunch without Clear Data; Ctrl+W; D/S/C and ESC (including during text edit); Cancel returns to same text selection; SAF fonts import/folder/refresh; in-app updater; touch, trackpad, stylus, canvas, file open/save.
5. Check no trackpad two-finger gesture inadvertently clicks tools or drags the canvas while a menu is open. Report if the platform still drops generic-motion events before winit.

**STOP** before any permanent signing, merging or GitHub Releases; require explicit device confirmation and separate owner approvals.
