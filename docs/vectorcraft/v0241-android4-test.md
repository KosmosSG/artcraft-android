# VectorCraft v0.24.1-android.4 — compact wheel customization (test only)

**Branch:** `fix/vectorcraft-v0241-android4-compact-wheel-ime-20261114`

This is an independently installable, disposable-signed ARM64 test APK, not a published release. Protect prior production releases, original signing keys and user data.

## Wheel dialog changes
- Replace the former full-screen, three-column customization window with a compact PhotoCraft-inspired settings dialog near the upper-left.
- Keep eight direction-specific slot selectors with readable labels and 206-point dropdowns; place controls, dividers and actions in a narrow panel. On smaller screens only the slot list scrolls.
- Render **actual-size live wheel preview on the canvas beside the settings window**, not inside that dialog. It tracks wheel size and opacity live and remains non-interactive.
- Adapt slider selections and Done button to Vc orange/maroon launcher colors; preserve maroon hub, thin orange rim, two-tone grey slots and existing icon artwork.
- New and Restore Default settings: **wheel size 84%, opacity 78%**, with 1% slider steps. Preserve previously saved user preferences rather than overwriting them automatically.
- Keep stylus-button activation, hover isolation, Ctrl+Z Undo, shortcuts and UI input routing unchanged.

## HONOR MagicPad 4 owner acceptance
1. Open Vc menu > Stylus Wheel > Customization. Verify compact dialog appears without spanning the screen, proper dropdown alignment and touch/trackpad scrolling in long dropdown lists.
2. Verify wheel appears **outside** the dialog on the canvas; drag Size and Opacity sliders and confirm preview matches actual wheel size/opacity, without selection or highlight of objects underneath.
3. Check default 84% / 78% on fresh test install and Restore Default; alter both sliders, close/reopen and confirm persistence.
4. Test Ctrl+Z Undo once per keypress, Ctrl+Shift+Z Redo, V/T/H and Esc, stylus-button wheel actions, touch pan and trackpad pinch.
5. **Existing separate failure remains open:** after Ctrl+Q and relaunch, imported `.ai` file Type editing can stop until app data is cleared. Reproduce and capture diagnostics; this UI-only candidate must **not** be described as fixing the failure. Do not clear data as part of test unless necessary after exporting logs.

Stop before merge, permanent signing, tag or publication.
