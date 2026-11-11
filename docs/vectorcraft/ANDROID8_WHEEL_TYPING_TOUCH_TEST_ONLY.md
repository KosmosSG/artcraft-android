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
