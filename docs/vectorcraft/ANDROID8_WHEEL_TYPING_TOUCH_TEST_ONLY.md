# VectorCraft Android.8 — Proposal A isolated test

Baseline: published `vectorcraft-v0.23.0-android.7`, source `65056bbe58acc8ab60a83b5d3ccbdda5e5745491`. Official upstream and builder pins unchanged.

- Opt-in, persisted Stylus Wheel row with checkmark in Vc menu. Eight actions: Select, Nodes, Pen, Type, Shapes (Rectangle), Hand, Undo, Redo.
- PhotoCraft's verified Magic-Pencil 4s device routing, single press to open/cancel, double press quick Eraser, tip to select, Escape to cancel. Text editing, dialogs and menus block wheel actions. Ordinary keyboard arrows remain unaffected.
- Approved Vc SVG letterforms in a burgundy circular hub with orange outline/highlight, soft shadow, 40×25 center mark and auto-hiding message. Reuses VectorCraft's actual tool icons.
- Touchscreen native translation and early fallback follow fingers in both axes. Trackpad direction, pinch and popup routing remain baseline behavior.
- Completes real Android IME resets: forward request ID to Java, invalidate old InputConnections, remove composition and restart input, then emit matching completion before accepting new input. Previously the pinned backend ignored the ID and toggled hide/show only. This addresses a confirmed missing reset-fence response; the reported imported-file failure still needs reproduction with the owner's file.

Build is ARM64 only, stripped symbols, separate `com.artcraft.vectorcraft.test` package, disposable signing, no production keys, no release publication.

## Device checks

1. Open the affected `.ai`; edit existing editable text and create new text. Try hardware keyboard and Gboard. Confirm save/reopen preserves edits. Outlined artwork is not an editable text node.
2. New document: type, select text, move caret, change text objects, ESC, V/T/P, Ctrl+W D/S/C repeatedly.
3. Two-finger touch: left/right/up/down moves artwork in the same direction. Pinch before/after pan; lift both fingers and repeat. Trackpad/menu behavior stays unchanged.
4. Vc → Stylus Wheel: checkmark follows toggle and survives relaunch. Test all eight actions; Shapes selects Rectangle. Single press/cancel, double press Eraser, tip selection without canvas marks, ESC, screen edges.
5. Wheel must not activate while typing, composing, in dialogs, or while the pen is drawing. Physical keyboard arrows still navigate normally.
6. Ctrl+Q/relaunch ten times; fonts, shared fonts, updater, Appearance, save and import regressions.

Local verification: all baseline Python checks passed (128 tests, one skipped); baseline plus new adapter/source overlays apply to pinned sources; native queue and reset patches apply to pinned vendor sources. ARM64 compilation and on-device behavior pending.
