# VectorCraft v0.24.1-android.6 — PhotoCraft-style wheel parity (TEST ONLY)

**Base:** Android.5 verified updater test source on `feature/vectorcraft-v0241-android5-inapp-updater-20261114`, itself based on Android.4 compact wheel and Android.3 Ctrl+Z. Official VectorCraft v0.24.1 pinned upstream, no production signing or release.

## Approved PhotoCraft reference

The supplied PhotoCraft screenshot shows a compact top-left dark dialog, eight slot dropdowns, subtle grey segment wedges, soft shadow, round brand hub and a single capsule notification centered near the bottom. Follow that visual language, **not its Photoshop tool commands or blue Pc theme**:

- Retain the exact approved Vc launcher-mark artwork in a maroon circular hub with orange lettering and hub border.
- Rework eight wheel segments to alternate charcoal gray `#2b2b2d` and `#313133`, with restrained divider strokes, lighter icons and readable labels. Keep the subdued Vc-orange outer hairline, orange hover highlight and soft feathered shadow.
- Compact **Stylus Wheel — Default** window, eight **Slot 1–Slot 8** selectors, single caption per position, orange-accent sliders, editable percent controls and no oversized internal wheel image.
- Change an assigned tool by swapping with its occupied slot if needed, like PhotoCraft. Persist assignments on change.
- Draw the actual-size live wheel preview on the canvas **outside the dialog**, without choosing or highlighting document objects under it.
- Restore Default uses **84% wheel size / 78% opacity** on fresh install; preserve custom existing saved settings until the owner resets.
- Bottom-center notification should match screenshot's soft, horizontal charcoal pill (450 × 38 points), appear briefly then fade; keep pen hover + single button opening, double-press Eraser behavior, input isolation, CTRL+Z and ctrl+Q handling unchanged.

## HONOR MagicPad 4 acceptance

1. Vc menu → Stylus Wheel → Customization: verify compact aligned rows, PhotoCraft-like window, dropdown/trackpad scrolling and absence of internal wheel preview.
2. Adjust wheel size and opacity; wheel preview beside dialog changes immediately, matches the real wheel, and does not select objects underneath.
3. Reset defaults = 84/78; close and reopen; persist. Change a tool used by another slot: the positions swap.
4. Wheel press/hover, correct eight dual-tone greys, Vc hub, thin orange rim, soft shadow, refined icon contrast.
5. Bottom-center toast like PhotoCraft, including appropriate fade and no UI blocking.
6. Regression: Ctrl+Z Undo, Ctrl+Shift+Z Redo, keyboard Type/V/P, ESC, Ctrl+W D/S/C, touch/trackpad pan/pinch; in-app updater UI still checks releases but **separate test app cannot install production APK**.
7. **Still known unresolved:** imported `.ai` text stops editing after Ctrl+Q/relaunch on device; do not claim fixed. Do not clear user data or alter stable releases.

**Stop at separate-install temporary-signed ARM64 TEST APK. Do not tag, release, production-sign or overwrite.**
