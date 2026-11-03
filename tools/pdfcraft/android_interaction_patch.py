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
            // Android keyboard covers may send a key event with stale Ctrl
            // metadata after Ctrl+W, or deliver printable D/C/S as Text.
            // The save prompt is already modal (app/keys.rs); consume exactly
            // the first matching event here, independent of stale modifiers.
            let answer = i.events.iter().enumerate().find_map(|(index, event)| {
                let key = match event {
                    egui::Event::Key { key, pressed: true, .. } => Some(*key),
                    egui::Event::Text(text) | egui::Event::Ime(egui::ImeEvent::Commit(text))
                        if text.eq_ignore_ascii_case("d") => Some(Key::D),
                    egui::Event::Text(text) | egui::Event::Ime(egui::ImeEvent::Commit(text))
                        if text.eq_ignore_ascii_case("c") => Some(Key::C),
                    egui::Event::Text(text) | egui::Event::Ime(egui::ImeEvent::Commit(text))
                        if text.eq_ignore_ascii_case("s") => Some(Key::S),
                    _ => None,
                }?;
                match key {
                    Key::D => Some((index, Some(false))),
                    Key::C => Some((index, None)),
                    Key::S => Some((index, Some(true))),
                    _ => None,
                }
            });
            if let Some((index, decision)) = answer {
                i.events.remove(index);
                return Some(decision);
            }
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
        // PDFCRAFT_ANDROID_REPEAT_VH: focus metadata for a form can persist
        // after leaving the actual editor. On Android, actual text-edit focus
        // is the authoritative guard; never steal typed text.
        let free = self.dialog.is_none() && self.close_request.is_none()
            && !self.palette_open && !keyboard_busy
            && (cfg!(target_os = "android") || self.views[i].forms.focus.is_none());""")

# PDFCRAFT_ANDROID_VH_EVENT_FALLBACK:
# Android physical covers sometimes produce Key without populating keys_down
# across a modal/IME transition. Read the actual Key/Text/IME event; check the
# event's own modifiers, not just a possibly stale global modifier snapshot.
change(keys,
"""        if !free || !plain {
            return;
        }""",
"""        if !free || (!plain && !cfg!(target_os = "android")) {
            return;
        }""")
change(keys,
"""        if ctx.input(|input| input.key_pressed(Key::V)) {
            self.quick_tool = QuickTool::Select;
            self.space_hand = None;
        }
        if ctx.input(|input| input.key_pressed(Key::H)) {
            self.quick_tool = QuickTool::Hand;
            self.space_hand = None;
        }""",
"""        // PDFCRAFT_ANDROID_VH_EVENT_FALLBACK: live keyboard event, never
        // ctrl-chord, never while a text editor or dialog owns keyboard focus.
        let android_key = if cfg!(target_os = "android") {
            ctx.input(|input| input.events.iter().find_map(|ev| {
                let candidate = match ev {
                    egui::Event::Key { key, pressed: true, modifiers, .. }
                        if !modifiers.ctrl && !modifiers.command
                            && !modifiers.alt && !modifiers.mac_cmd && !modifiers.shift =>
                        Some(*key),
                    egui::Event::Text(text) | egui::Event::Ime(egui::ImeEvent::Commit(text))
                        if input.modifiers.is_none() && text.eq_ignore_ascii_case("v") =>
                        Some(Key::V),
                    egui::Event::Text(text) | egui::Event::Ime(egui::ImeEvent::Commit(text))
                        if input.modifiers.is_none() && text.eq_ignore_ascii_case("h") =>
                        Some(Key::H),
                    _ => None,
                };
                match candidate { Some(Key::V) => Some(Key::V), Some(Key::H) => Some(Key::H), _ => None }
            }))
        } else { None };
        if android_key == Some(Key::V)
            || (!cfg!(target_os = "android") && ctx.input(|i| i.key_pressed(Key::V)))
        {
            self.quick_tool = QuickTool::Select;
            self.space_hand = None;
        } else if android_key == Some(Key::H)
            || (!cfg!(target_os = "android") && ctx.input(|i| i.key_pressed(Key::H)))
        {
            self.quick_tool = QuickTool::Hand;
            self.space_hand = None;
        }""")

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

# PDFCRAFT_ANDROID_DCS_MODAL_FALLBACK: the upstream shortcut phase runs
# before the modal is rendered; read keys at the displayed modal too.
# Only the existing unsaved-close prompt invokes this branch.
change(prompts,
"""    if choice.is_none() && modal.should_close() {
        choice = Some(None);
    }
    if let Some(c) = choice {
        app.resolve_close(ctx, c);
    }
}""",
"""    // PDFCRAFT_ANDROID_DCS_MODAL_FALLBACK: only the save prompt consumes
    // D/C/S, never any other dialog or text field behind this modal.
    #[cfg(target_os = "android")]
    if choice.is_none()
        && app.pending_link.is_none()
        && app.pending_remote_link.is_none()
        && app.pending_full_screen.is_none()
        && !app.updates.open
        && app.dialog.is_none()
        && app.unlock_prompt.is_none()
    {
        choice = save_prompt_key(ctx, &mut app.save_prompt_button);
    }
    if choice.is_none() && modal.should_close() {
        choice = Some(None);
    }
    if let Some(c) = choice {
        app.resolve_close(ctx, c);
    }
}""")

print("PASS: PDFCraft D/C/S modal fallback, V/H keys and touch selection hint")
