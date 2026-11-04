# PhotoCraft v0.20.1-android.2 keyboard candidate

This is an unverified device-test candidate, not a production release or a claim
that the HONOR keyboard failure is fully resolved.

## Source findings

The previous Java helper accepted A–Z, but `dispatchKeyEvent` still called it
only inside the original V/T/B/Y/N/C/W/D/S/Enter/Escape gate. Keys such as M
therefore depended on another route seeing them.

The bridge discarded a Java transition when a matching native key was present.
That also discarded authoritative Android modifier flags. The native modifier
reconstruction runs *before* bridge injection, not after it: the defect is loss
of Java flags on a native match, not overwriting every injected key.

The adapter captured hardcoded tool IDs before upstream dispatch and invoked
them after upstream logic. That second dispatcher could overwrite custom
bindings or group selection. Logging `Ok` from it did not establish the final
selected tool or prove a unique execution.

The Escape fallback ran in the logic tail, before the UI tail, and the separate
save/discard queue guessed answers from Text events. Both bypassed ownership
decisions made by the normal editor/dialog handlers.

## Candidate changes

- Forward all supported letters and physical modifier transitions from Activity.
- Reconcile Java modifier flags with native events and emit ModifiersChanged.
- Use upstream shortcut preferences, modal checks, and tool selection only.
- Remove Text-to-key guessing and the independent Y/N/C answer queue consumer.
- Run the Escape fallback after the editor UI has processed the pass, then
  release the hidden IME if editing ended.
- Show JNI transition counts, upstream command outcomes, and actual tool states
  before/after logic and UI. Suppress diagnostic key names during text editing.

Changes are applied to a disposable upstream/adapter checkout by a final overlay.
The production adapter, shared templates, protected release and signing keys are
not changed. The test package remains `com.artcraft.photocraft.candidate`.

## Validation and limits

The standalone Rust test crate compiles the exact replacement keyboard bridge
against egui 0.37. Tests cover native/Java duplicate reconciliation with Ctrl,
20 routing cycles with key releases and Shift, text-input protection, actual
egui Ctrl+W consumption exactly once, and modifier release without another key.
These are routing tests; they do not simulate 20 complete document-edit cycles.

The full overlay chain is applied locally to the pinned upstream commit and the
protected baseline source gate is checked. The workflow repeats bridge tests
before compiling and verifies APK package, ABI, ZIP integrity and non-production
certificate. Check its result before treating an APK as available.

Still unverified: device event timing across native/Java frame boundaries,
IME-reset acknowledgements, real text preservation, Y/N/C save completion,
custom bindings and spring-tool behavior on the tablet, and fonts/AI/touch/
trackpad regressions. A no-op winit reset shim remains in the existing branch;
this candidate does not pretend to implement a complete IME-reset protocol.

## HONOR MagicPad 4 checklist

1. Keep stable PhotoCraft installed. Open the separate PhotoCraft Test app and
   create a temporary document. Confirm About shows android.2.
2. Press M, V, B, T and check the actual highlighted tool after each key.
3. Click the canvas, type a distinctive sentence, then Escape. Confirm the
   sentence remains intact and editing ends without selecting another tool.
4. Immediately press M, V, B, H, Z. Repeat steps 3–4 twenty times.
5. Test a custom binding and Shift tool cycling; normal text must not select tools.
6. In separate dirty temporary documents, test Ctrl+W then C, Y, and N. Verify
   C retains the document, Y saves via the picker, and N discards only that
   explicitly selected temporary document. Also cancel the save picker.
7. Switch between canvas, properties, toolbar, text fields and dialogs. Check
   Ctrl/Shift release, touch input, and two-finger trackpad scrolling.
8. Check imported/system fonts, refresh, AI Tools and updater controls.
9. If a shortcut fails, enable Pc → Keyboard Diagnostics and capture the
   before/after tool states and routing lines without entering sensitive text.

Physical behavior can be marked PASS only after the owner tests the exact APK.


## Android.3 follow-up after owner video (4 November 2026)

Android.2 failed the owner's Escape test: Type editing remained true and subsequent
M/B/V letters were inserted as text. Earlier no-editor presses showed only the
ambiguous `JNI received` counter, not a decoded DOWN. This establishes a failed
candidate, not the exact Android action/repeat values.

The Java repeat filter rejected every DOWN with nonzero repeatCount. Android.3
uses a per-device/key/downTime gate: the first observed DOWN is delivered even
if marked repeated, subsequent held repeats and duplicate callback routes are
suppressed, and releases/focus changes retire the held state. It never invents a
DOWN from a release. This covers a reproducible routing gap; whether MagicOS
triggers that gap in the recording is still a hypothesis pending new diagnostics.

Diagnostics now show DOWN/UP and repeat count in Java and Escape at the native,
post-bridge, queued-editor and UI-tail stages even while typing. Other typed key
names remain suppressed. `JNI polled` explicitly means queue records, not proof
that a press was decoded. No typed text or document contents are logged.

The exact Java gate passes 20 synthetic Escape/M cycles including a first-observed
repeat, duplicate routes, missing release, stale release and focus reset. The
existing five Rust routing tests are repeated by CI. Device Escape success is
still NOT verified. Test a short sentence → Esc → M/B/V; if it fails, capture the
new Escape lines. Keep the stable app; this remains a temporary-signed candidate.
