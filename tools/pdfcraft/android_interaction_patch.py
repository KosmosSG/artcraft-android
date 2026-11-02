#!/usr/bin/env python3
"""PDFCraft v0.17 Android-only D/C/S save dialog, and repeatable tool keys.

All anchors fail closed when upstream source changes. Desktop behavior unchanged.
Apply after android_canvas_input_patch.py to the checked staging source.
"""
from pathlib import Path
import sys
src=Path(sys.argv[1])
def change(path: Path, old: str, new: str):
    text=path.read_text()
    if new in text:
        return
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"PDFCraft v0.17 input patch: expected one anchor {old[:70]!r} in {path}; got {n}")
    path.write_text(text.replace(old,new,1))

prompts=src/"crates/ui-egui/src/dialogs/prompts.rs"
change(prompts,
"""        if i.consume_key(Modifiers::NONE, Key::Escape) {
            return Some(None);
        }
        if [(Modifiers::COMMAND, Key::D)""",
"""        if i.consume_key(Modifiers::NONE, Key::Escape) {
            return Some(None);
        }
        // ARTCRAFT_ANDROID_DCS: These plain letters are active ONLY while the
        // unsaved-changes modal is open (called from app/keys.rs close_request).
        // They must never operate when editing PDF text or another dialog.
        #[cfg(target_os = "android")]
        {
            if i.consume_key(Modifiers::NONE, Key::D) { return Some(Some(false)); }
            if i.consume_key(Modifiers::NONE, Key::C) { return Some(None); }
            if i.consume_key(Modifiers::NONE, Key::S) { return Some(Some(true)); }
        }
        if [(Modifiers::COMMAND, Key::D)""")
change(prompts,
"""widgets::pill_button_marked(ui, tl!("Save"), true, chosen == PromptButton::Save)""",
"""widgets::pill_button_marked(ui, &if cfg!(target_os = "android") { format!("{} (S)", tl!("Save")) } else { tl!("Save").to_owned() }, true, chosen == PromptButton::Save)""")
change(prompts,
"""widgets::pill_button_marked(ui, tl!("Cancel"), false, chosen == PromptButton::Cancel)""",
"""widgets::pill_button_marked(ui, &if cfg!(target_os = "android") { format!("{} (C)", tl!("Cancel")) } else { tl!("Cancel").to_owned() }, false, chosen == PromptButton::Cancel)""")
change(prompts,
"""widgets::pill_button_marked(ui, tl!("Don't save"), false, chosen == PromptButton::DontSave)""",
"""widgets::pill_button_marked(ui, &if cfg!(target_os = "android") { format!("{} (D)", tl!("Don't save")) } else { tl!("Don't save").to_owned() }, false, chosen == PromptButton::DontSave)""")
keys=src/"crates/ui-egui/src/app/keys.rs"
change(keys,
"""        let free = self.dialog.is_none() && !self.palette_open && !ctx.egui_wants_keyboard_input() && self.views[i].forms.focus.is_none();""",
"""        // ARTCRAFT_ANDROID_REPEAT_TOOL_KEYS: EgUI's global keyboard-focus
        // hint can remain true after touching the document or dismissing a
        // widget, leaving H/V working exactly once. Only an actual focused
        // text field/form must suppress bare tool keys on Android.
        let keyboard_busy = if cfg!(target_os = "android") {
            ctx.text_edit_focused()
        } else {
            ctx.egui_wants_keyboard_input()
        };
        let free = self.dialog.is_none() && self.close_request.is_none()
            && !self.palette_open && !keyboard_busy
            && self.views[i].forms.focus.is_none();""")
# App already has tool_keys(), so remove a redundant Android-only H/V consumer
# added in the previous candidate. Keeping both listeners can mask key release
# timing and interfere with repeat shortcuts after the first document close.
app=src/"crates/ui-egui/src/app.rs"
change(app,
"""        self.shortcuts(ctx);
        #[cfg(target_os = "android")]
        self.android_bare_tool_keys(ctx);
""",
"""        self.shortcuts(ctx);
        // ARTCRAFT_ANDROID_REPEAT_KEYS: upstream tool_keys() now uses precise
        // editor focus; avoid a second H/V consumer after shortcuts().
""")
canvas=src/"crates/ui-egui/src/canvas.rs"
change(canvas,
"""    let navigation_enabled = app.dialog.is_none() && app.close_request.is_none() && !app.palette_open && ui.is_enabled() && ui.input(|i| i.focused);""",
"""    // ARTCRAFT_ANDROID_TOUCH_HINT: finger users have no hover tooltip.
    #[cfg(target_os = "android")]
    // Avoid borrowing all of `app` while `app.views[index]` is mutably borrowed.
    // Read disjoint dialog state directly; equivalent to the modal gate here.
    if app.quick_tool == QuickTool::Select
        && app.close_request.is_none()
        && app.dialog.is_none()
        && !app.palette_open
    {
        let origin = ui.min_rect().min + egui::vec2(16.0, 12.0);
        egui::Area::new(egui::Id::new("pdfcraft-touch-select-hint"))
            .fixed_pos(origin)
            .order(egui::Order::Tooltip)
            .interactable(false)
            .show(ui.ctx(), |hint| {
                egui::Frame::group(hint.style())
                    .fill(hint.visuals().panel_fill)
                    .show(hint, |hint| {
                        hint.small("Touch: swipe to scroll • hold and drag to select");
                    });
            });
    }
    let navigation_enabled = app.dialog.is_none() && app.close_request.is_none() && !app.palette_open && ui.is_enabled() && ui.input(|i| i.focused);""")
print("PASS: PDFCraft D/C/S, repeatable tools and touch selection hint")
