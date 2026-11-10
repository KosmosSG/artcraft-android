# VectorCraft v0.23.0-android.4 — Batched touchpad axes and Ctrl+Q stage diagnosis

## Device-confirmed status (Android.3)
PASS: canvas/popup two-finger scroll without selection, native pinch AFTER scrolling, Gboard/physical Type tool, V/T/H/ESC, Ctrl+W D/S/C, five cold launches, fonts and updater.
FAIL: direct pinch without prior scroll, pinch after releasing both fingers, 10 consecutive Ctrl+Q quit/reopen without clearing data.

## Scoped implementation
1. Correct Android 14+ touchpad single-pointer events. Accumulate **every historic AXIS_GESTURE_SCROLL_X_DISTANCE (50), SCROLL_Y_DISTANCE (51) and PINCH_SCALE_FACTOR (52)** then current sample, exactly once. Pinch scale is multiplicative, combined through log sums; scroll distances are additive. Use valid API 34 gesture classifications even if OEM source flags are ambiguous. Retain native event ordering and two-pointer fallback only when real 2-pointer pad data arrives. Do not create synthetic frame loops or apply extra wheel multipliers.
2. Add source-route counters: classified pinch, classified scroll, packets with historical pinch samples, unclassified/no-axis trackpad moves. These reset at Diagnostic Session > Start / Reset. Keep old five existing counters; no pointer coordinates, text, documents, or filenames.
3. Ctrl+Q is **NOT FIXED YET**. Preserve Android.2 native-first shutdown, upstream Save Changes D/S/C and on_exit persistence. Add persistent, whitelisted VC_QUIT4 milestones at native_close_requested, native_loop_returned, java_finish_requested/enter, on_destroy_enter/return. The app's next diagnostic snapshot shows the last milestone under prior_process_stage, even if the previous attempt ANRed and required a force-stop to relaunch. This identifies the blocked stage without bypassing save prompts or killing the process.
4. Unit tests cover batched native axis history, scale product, scroll sum, invalid samples, direct-pinch recognition and pan hysteresis. Cheap source compatibility preflight runs before expensive ARM64 compile.

## HONOR MagicPad 4 device acceptance
- Begin with freshly opened file and **pinch immediately before any scroll**. Reset diagnostic session to zero before each gesture type, copy report after failing/succeeding. Then lift two fingers completely; try pinch again; then pan followed by pinch.
- Canvas/popup trackpad scroll should remain smooth with no selection; touch/stylus unaffected.
- Ctrl+Q → reopen 10x, Welcome/new/edited file, ensure Ctrl+W D/S/C and Cancel still correct. After any freeze/relaunch failure, do not clear app data; force-stop only if necessary to relaunch, then open diagnostics and copy prior_process_stage. If still unknown, obtain Android bug report with VC_QUIT4 log lines.
- Preserve typing/shortcuts, five cold starts, fonts and updater.

## Security and release gate
Dedicated disposable-key-signed, ARM64-only com.artcraft.vectorcraft.test with version v0.23.0-android.4 and versionCode 16783904. Prior stable production release and Android.3 test remain untouched. No permanent signing, merge, tag or publication before explicit user device PASS.