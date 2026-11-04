#!/usr/bin/env python3
"""PDFCraft-only Android touch-selection and bare tool-key bindings, v0.17.0.

Touch scroll in Select mode is a distinct operation from one-finger text
selection. This patch disables ScrollArea's one-finger touch-drag capture in
Android only; the winit gesture adapter owns TWO-finger scrolling.
Tooltips in the core toolbar display H for Hand although H is not present in
the central keyboard command registry. Install H and V in the real app's
shortcut phase without stealing text-entry or Ctrl/Alt shortcuts.
"""
import sys
from pathlib import Path

source = Path(sys.argv[1])
canvas = source / "crates/ui-egui/src/canvas.rs"
app = source / "crates/ui-egui/src/app.rs"
def one(text, before, after, label):
    count = text.count(before)
    if count != 1:
        raise ValueError(f"{label} changed (expected 1 anchor, found {count})")
    return text.replace(before, after, 1)

c = canvas.read_text()
mark = "PDFCRAFT_ANDROID_SELECT_TOUCH_NOT_SCROLL"
if mark not in c:
    c = one(c,
        """        } else {
            egui::scroll_area::DragScroll::OnTouch
        },""",
        """        } else if cfg!(target_os = "android") {
            // PDFCRAFT_ANDROID_SELECT_TOUCH_NOT_SCROLL: Select is for actual
            // one-finger text/annotation dragging on Android. With OnTouch,
            // the ScrollArea steals that drag before PDFCraft can select it.
            // Two-finger touch scrolling is handled in Android winit as wheel.
            egui::scroll_area::DragScroll::Never
        } else {
            egui::scroll_area::DragScroll::OnTouch
        },""", "canvas ScrollArea touch policy")
    canvas.write_text(c)
else:
    assert "egui::scroll_area::DragScroll::Never" in c

a = app.read_text()
mark = "PDFCRAFT_ANDROID_BARE_TOOL_KEYS"
if mark not in a:
    a = one(a, "        self.shortcuts(ctx);\n",
       "        self.shortcuts(ctx);\n        #[cfg(target_os = \"android\")]\n        self.android_bare_tool_keys(ctx);\n", "app keyboard shortcut phase")
    a += """
// PDFCRAFT_ANDROID_BARE_TOOL_KEYS. The toolbar advertises H and V, while
// the upstream registry contains Ctrl-based document commands only.
#[cfg(target_os = "android")]
impl PdfCraftApp {
    fn android_bare_tool_keys(&mut self, ctx: &egui::Context) {
        use egui::{Key, KeyboardShortcut, Modifiers};
        if self.modal_open() || self.palette_open || ctx.text_edit_focused() {
            return; // Never change tools while typing or answering a dialog.
        }
        // Ignore Ctrl/Shift/Alt/Command chords, including Ctrl+H and Ctrl+V:
        // these belong to registered PDFCraft commands or the text editor.
        let shortcuts_allowed = ctx.input(|i| {
            !i.modifiers.ctrl && !i.modifiers.shift && !i.modifiers.alt
                && !i.modifiers.command && !i.modifiers.mac_cmd
        });
        if !shortcuts_allowed { return; }
        if ctx.input_mut(|i| i.consume_shortcut(&KeyboardShortcut::new(
            Modifiers::NONE, Key::H
        ))) {
            self.quick_tool = QuickTool::Hand;
        } else if ctx.input_mut(|i| i.consume_shortcut(&KeyboardShortcut::new(
            Modifiers::NONE, Key::V
        ))) {
            self.quick_tool = QuickTool::Select;
        }
    }
}
"""
    app.write_text(a)
else:
    assert "android_bare_tool_keys" in a

print("PASS: PDFCraft Android Select one-finger text drag; H/V native tools without Ctrl chord regression")
