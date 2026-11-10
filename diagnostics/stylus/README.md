# ArtCraft Stylus Diagnostic — TEST ONLY

This is a standalone Java Android APK for HONOR Magic-Pencil 4s and MagicPad 4. It does not alter any ArtCraft editor, shared keyboard logic, production signing key, updater or release.

## Capabilities

- Live hover enter/move/exit detection and yellow hover crosshair.
- Pressure-sensitive drawing, raw pressure/tilt/distance/tool-type values.
- Stylus primary/secondary/secondary-button edges and Android button press/release actions.
- Single, double and long press classification when Android exposes actual press/release state changes.
- Raw unattributed KeyEvent logging, including device/source/scan code, in case MagicOS emits pen events as keys.
- User-triggered text log export using the Android document picker. No Internet, storage, accessibility or background collection permission.
- Capped in-memory event log (2,500 rows) and throttled movement sampling.

## Install and test

From the GitHub Actions workflow named ArtCraft Stylus Diagnostic ARM64 TEST ONLY, open a successful run and download the ArtCraft-Stylus-Diagnostic-TEST-ONLY artifact. Extract the ZIP and install the TEST-ONLY APK.

1. Check Magic-Pencil 4s in HONOR Notes first.
2. Hover over the dark canvas with no contact; look for the yellow crosshair and HOVER actions.
3. Draw light and heavy strokes. Check pressure values; tilt and draw again and check tilt values.
4. Hover and click the pen button once, twice quickly, and hold for at least 650 ms.
5. Repeat button tests while drawing and while pressing the pen onto the screen.
6. Check BUTTON_EDGE and raw KEY_EVENT_UNATTRIBUTED entries. Raw keyboard events do not prove they came from the pen. MagicOS may intercept unsupported gestures entirely.
7. Export the text log. It contains local timestamps and screen coordinates; review before sharing.
8. Try again after locking/unlocking and relaunching.

## Safety

- Separate package: com.artcraft.stylusdiagnostic
- Workflow has read-only content permission and uploads a short-lived Actions artifact only.
- Signing certificate is generated from a random disposable secret in runner temp storage and not copied to the artifact.
- Future test rebuilds may require uninstalling this diagnostic app because their signing certificates will differ.
- No GitHub Release publishing, PR merging, stable signing or permanent key use.
- This experiment is a utility, not a registered ArtCraft editor.
