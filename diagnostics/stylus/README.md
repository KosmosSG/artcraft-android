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

## v0.1.1 diagnostic correction

The first MagicPad 4 report showed one HOVER_ENTER (tilt 0.446), no contact/button transitions and 18 raw key events (DPAD_UP/DOWN and fingerprint identify) from another device ID. Device IDs are session-specific and are not proof of stylus origin.

Fix: no longer retain a MotionEvent object across dispatches; Android can recycle and reuse these objects. Log motion centrally at Activity dispatch to avoid duplicate callbacks, record InputDevice name/vendor/product/source/keyboard/external metadata, count non-stylus touch starts/ends, and add a Mark step button to correlate press sequences with key events. Hardware compatibility still requires the next on-device test.

Press **Mark step**, then only press the Magic-Pencil side button while hovering. Repeat with pen touching the canvas, then test without a connected keyboard or trackpad. Inspect the INPUT_DEVICE rows for names corresponding to source IDs; no automatic macro mapping is performed.

## v0.1.2 visual drawing fix

User video showed isolated blue dots rather than connected lines even while 330 pressure/contact samples arrived. Fix the app: capture the raw stylus drag stream in Activity dispatch before the parent ScrollView intercepts it, map raw screen coordinates into canvas-local coordinates, keep ScrollView from stealing an active pen stroke, and render connected pressure-width line segments (including MotionEvent history). Log CANVAS_STROKE_START/END for confirmation. Keep all hover, tilt, export, keyboard and device metadata unchanged. Device 109 is explicitly identified by Android as `HONOR Magic-Pencil 4s Mouse` and emits DPAD_UP/DOWN; this is evidence of a pen-associated input device, not a proven press-to-action mapping.

## v0.1.3 — Pen must not scroll the diagnostic page

Fix reported MagicPad 4 regression: page scrolls vertically while user draws with Magic-Pencil 4s, preventing comfortable pen strokes. The scrollable outer UI now uses a stylus-safe ScrollView subclass: it never intercepts or consumes stylus touch motion (finger scrolling remains normal). Additionally the diagnostic logs and consumes DPAD_UP/DOWN only from an Android input device named HONOR Magic-Pencil 4s, preventing a pen-associated key event from navigating/scrolling the page. The log gains PEN_NAVIGATION_SCROLL_BLOCKED evidence. Other keyboard devices are left alone, and no macro is executed. Continuous pressure-sensitive lines, hover, tilt, and SAF text export are preserved. Check drawing visually on tablet; successful compilation alone is not device verification.

## v0.1.4 — Four labeled pen-button test windows

The previous marked log contained three labels but only incomplete DPAD_UP/DOWN press-release pairs. To make the next session actionable, add four explicit controls: Single hover (9s), Double hover (9s), Long hover (11s), and Press while drawing (11s). Each disabled-all-others timed capture writes TEST_BEGIN, timestamped TEST_PEN_KEY rows, and TEST_END with per-test key down/up, matched pair, unmatched-release, unmatched-press, sustained >=1400ms, standard stylus button edge, and simultaneous pen contact counts. Missing events are reported; no silent guesses, macro playback or injection. Pen-specific key identification uses device name (not hardcoded numeric id) and preserves scroll isolation. The device's MagicOS layer may only supply orphan UP events even when physical gestures work. Export contains TEST_SUMMARY_BEGIN/END and the full latest raw log. The UI remains finger-scrollable outside canvas, and pen movement cannot scroll. This is an isolated test APK, disposable signing, no publication.

## v0.1.5 — five-repeat Magic-Pencil 4s calibration
Starting from v0.1.4 and retaining all verified stylus drawing, hover, pressure,
tilt, pen-scroll isolation, finger scrolling, raw KeyEvent capture and SAF export.
Four on-screen controls select Single Hover, Double Hover, Long Hover, or Press
While Drawing. Selecting a category immediately starts trial 1/5, followed by
a dedicated "Record next trial" button between attempts. Each trial lasts 8s
for single/double or 10s for long/drawing, and explicitly logs
CALIBRATION_TRIAL_BEGIN, CALIBRATION_PEN_KEY, CALIBRATION_TRIAL_END with event
signature, matching/missing press-release pairs, app-visible duration and
simultaneous stylus touch samples. Results aggregate five per gesture, report
repeatability of observed event signatures rather than claiming OS-independent
gesture recognition, and flag if single/double share the same dominant pattern.
Export includes durable trial and per-gesture aggregate summaries independent
of the last 8000 raw event rows. Existing published ArtCraft editors stay untouched.
No permissions, macro execution or automated input injection.

## v0.1.6 — One-shot signal calibration

Preserves the v0.1.5 five-attempt controls and the v0.1.3 pressure/tilt/hover, drawing, pen scroll protection and finger scroll behavior. A trial now begins on user selection and records only the **first** observed pen-associated keyboard signal or standard stylus button edge. It auto-closes after a 450ms grace period (or after 8–10 seconds without a signal). An UP-only key is intentionally retained as an orphan-release observation, not reconstructed into a press; a DOWN-first signal can capture its matching UP. Extra key events in the grace interval are explicitly counted as ignored and preserved in raw logs, but not included in the calibrated signature. Per-trial results include close reason, first code, elapsed time, first source, excluded extras, and matched/unmatched edges. No software macros, automatic keybinding, OS-wide permissions, production APK edits or signing.

Test instruction: perform the requested physical gesture **once in each trial** and wait for the automatic completion. Tap Record next trial until 5/5 for each category, then export text. Confirm drawing, tilt, hover and scrolling remain intact.
