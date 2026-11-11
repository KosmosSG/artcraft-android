# VectorCraft Android.8 — Proposal A isolated test

Baseline: published `vectorcraft-v0.23.0-android.7`, source `65056bbe58acc8ab60a83b5d3ccbdda5e5745491`. Official upstream and builder pins unchanged.

- Opt-in, persisted Stylus Wheel row with checkmark in Vc menu. Proposal A default remains Select, Nodes, Pen, Type, Shapes (Rectangle), Hand, Undo, Redo.
- **Customize Stylus Wheel…** in the Vc menu opens a native egui settings window. Choose any existing action per one of eight labeled radial positions: Select, Nodes, Pen, Type, Shapes, Hand, Undo, Redo, Eraser, Pencil, Ellipse, or Zoom. Every slot is customizable; duplicate selections are allowed. Settings persist in the app's Android SharedPreferences and are validated on load. **Reset to Proposal A** restores the exact original eight positions. The stylus double-press Eraser shortcut remains unchanged.
- PhotoCraft's verified Magic-Pencil 4s device routing, single press to open/cancel, double press quick Eraser, tip to select, Escape to cancel. Text editing, dialogs and menus block wheel actions. Ordinary keyboard arrows remain unaffected.
- Approved Vc SVG letterforms in a burgundy circular hub with orange outline/highlight, soft shadow, 40×25 center mark and auto-hiding message. Reuses VectorCraft's actual tool icons.
- Touchscreen native translation and early fallback follow fingers in both axes. Trackpad direction, pinch and popup routing remain baseline behavior.
- Completes real Android IME resets: forward request ID to Java, invalidate old InputConnections, remove composition and restart input, then emit matching completion before accepting new input. Previously the pinned backend ignored the ID and toggled hide/show only. This addresses a confirmed missing reset-fence response; the reported imported-file failure still needs reproduction with the owner's file.

Build is ARM64 only, stripped symbols, separate `com.artcraft.vectorcraft.test` package, disposable signing, no production keys, no release publication.

## Device checks

1. Open the affected `.ai`; edit existing editable text and create new text. Try hardware keyboard and Gboard. Confirm save/reopen preserves edits. Outlined artwork is not an editable text node.
2. New document: type, select text, move caret, change text objects, ESC, V/T/P, Ctrl+W D/S/C repeatedly.
3. Two-finger touch: left/right/up/down moves artwork in the same direction. Pinch before/after pan; lift both fingers and repeat. Trackpad/menu behavior stays unchanged.
4. Vc → Stylus Wheel: checkmark follows toggle and survives relaunch. Test all eight Proposal A actions; Shapes selects Rectangle. Single press/cancel, double press Eraser, tip selection without canvas marks, ESC, screen edges.
5. Vc → Customize Stylus Wheel…: assign each of the eight slots to different features (including Pencil, Eraser, Ellipse, Zoom), verify correct command and icon on every wedge, close/reopen settings, quit/relaunch and verify persistence, then use Reset to Proposal A. Test editing preferences while the wheel is disabled.
6. Wheel must not activate while typing, composing, in dialogs, or while the pen is drawing. Physical keyboard arrows still navigate normally.
7. Ctrl+Q/relaunch ten times; fonts, shared fonts, updater, Appearance, save and import regressions.

Local verification: all baseline Python checks passed (128 tests, one skipped); baseline plus new adapter/source overlays apply to pinned sources; native queue and reset patches apply to pinned vendor sources. ARM64 compilation and on-device behavior pending.

## Android.8 Vc menu visibility regression (HONOR MagicPad 4)

A screenshot of the installed `com.artcraft.vectorcraft.test` Android.8 app showed that tapping the top-left Vc icon opened the compact Android launcher menu with fonts, updates, appearance, Touch Shortcut Pad and diagnostics, **but not** the Stylus Wheel or its customizer. The Android.8 patch initially registered the commands in `menus/tree.rs` only; the compact icon invokes `android_vc_menu` in `menus.rs` directly and does not render those tree entries.

Test-only correction: insert the checkbox-backed **Stylus Wheel** toggle and **Customize Stylus Wheel…** action into the actual Android Vc launcher menu, next to Touch Shortcut Pad, preserving the existing font, updates, appearance and keyboard entries. The toggle uses the same persisted JNI/SharedPreferences state and Android menu bit 256; Customize uses bit 512. Add a CI assertion that checks `android_vc_menu` in the staged `menus.rs`, not only the tree, before compiling the APK.

Device tests: confirm both entries visibly appear; toggle shows a check and stays checked after relaunch, opens wheel only on stylus input; Customize opens even while disabled, eight slot settings persist, Reset to Proposal A works, and existing entries continue to work.

## Consolidated Android.8 touch, opened text and APK-size correction (2026-11-12)

Evidence: user recorded an existing `.ai` file (Crafticon V2.ai) with selected live text and Type controls visible, but keystrokes did not alter the selected artwork. Creating a new document and typing worked. This suggests an imported document hit-target/edit-activation or IME focus transition; actual root cause cannot be confirmed from a recording alone. Scope the correction to Android: if direct hit-test does not yield a live Text node, allow the *already selected live Text node* only when a tap is within its transformed glyph layout; retain ordinary direct hits and unchanged desktop behavior. On real Type IME reset, restore visibility/focus of the hidden EditText only when `imeWanted`; leave other shortcut/dialog focus untouched. Keep ordered `ImeResetId` acknowledgements, no synthetic success.

Touchscreen: replace egui's potentially mixed touch/synthetic scroll delta with one two-contact canvas centroid source (raw `Touch` deltas if available, else `multi_touch.translation_delta`). Content follows fingers: swipe left/up moves artwork left/up, swipe right/down moves artwork right/down; trackpad events and pinch zoom stay unchanged. Never use synthetic pointer-button drags to pan.

Download optimization: previous Android.8 TEST APK was **163,407,944 bytes** (APK file; ZIP artifact was separately compressed). The new disposable test build keeps Rust release stripping, ARM64 only, splash, fonts, stylus and in-app updates, and configures Gradle `useLegacyPackaging = true` to compress `lib/arm64-v8a/libvectorcraft_android.so` inside the APK. Android extracts the shared library at installation. This should lower the APK download size, at the cost of additional install time/installed disk usage. Build gates check compression, signature, ZIP integrity and size reduction; no production config changes.

Device regression tests: (1) open Crafticon V2.ai, select existing live `Lc` text with Type and tap the glyph; confirm caret appears and typing modifies it, save and reopen; (2) new document typing still works, ESC exits editing; (3) two-finger touchscreen pan all four directions, including immediately on first movement; (4) trackpad two-finger scrolling, pinch zoom, popup menu scrolling unchanged; (5) top-left Vc menu shows Stylus Wheel checkbox and Customize entry, customization persists, pen-button wheel opens; (6) Ctrl+Q relaunch ten times and D/S/C, imported/shared fonts and in-app updater still work; (7) compare APK download size, installation behavior and cold-start speed on HONOR MagicPad 4. If selected content is outlined glyphs or locked paths rather than editable Text, edit the actual Text layer instead; do not alter outlined artwork.
