#!/usr/bin/env python3
"""Scoped WordCraft v0.14.0 D/C/S port for the split dialog modules.

Fail closed if upstream changes. Operates only on the ephemeral source checkout.
"""
from pathlib import Path

from patch_unsaved_dcs import HELPER

CHOICE = '    let answer = if ui.input(|i| i.key_pressed(egui::Key::Escape)) {'
WINDOW = '    let window = crate::window_close::window(ctx, egui::Window::new(tl!(title)).id(id).collapsible(false).resizable(false));'


def once(text: str, old: str, new: str, context: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"WordCraft v0.14.0 {context}: expected one anchor, got {count}")
    return text.replace(old, new, 1)


def apply(root) -> None:
    ui = Path(root) / "crates/ui-egui/src/dialogs"
    dispatch = ui / "dispatch.rs"
    chrome = ui / "chrome.rs"
    if not dispatch.is_file() or not chrome.is_file():
        raise ValueError("WordCraft v0.14.0 split dialog modules missing")

    original = dispatch.read_text(encoding="utf-8")
    start = original.index("fn save_changes_dialog(")
    end = original.index("\nfn insert_merge_field_dialog(", start)
    old = original[start:end]

    new = old
    new = once(new, 'ui.button(tl!("Cancel"))',
               'ui.button(format!("{} (C)", tl!("Cancel")))', "Cancel button")
    new = once(new, 'ui.button(tl!("Don\'t Save"))',
               'ui.button(format!("{} (D)", tl!("Don\'t Save")))', "Don't Save button")
    new = once(new, 'primary_button(ui, tl!("Save"))',
               'primary_button(ui, format!("{} (S)", tl!("Save")))', "Save button")
    replacement = '''    let queued = ui.ctx().data_mut(|data| data.remove_temp::<u8>(egui::Id::new("wordcraft.unsaved.dcs")));
    let shortcut = match queued.or_else(|| take_dcs(ui.ctx())).or_else(|| {
        ui.input(|i| {
            if i.modifiers.any() { None }
            else if i.key_pressed(egui::Key::D) { Some(1) }
            else if i.key_pressed(egui::Key::C) { Some(2) }
            else if i.key_pressed(egui::Key::S) { Some(3) }
            else { None }
        })
    }) {
        Some(1) => Some("dontSave"), Some(2) => Some("cancel"), Some(3) => Some("save"), _ => None,
    };
    let answer = if let Some(answer) = shortcut {
        Some(answer)
    } else if ui.input(|i| i.key_pressed(egui::Key::Escape)) {'''
    new = once(new, CHOICE, replacement, "D/C/S input")
    next_dispatch = original[:start] + new + original[end:] + HELPER

    original_chrome = chrome.read_text(encoding="utf-8")
    modal = '''    if matches!(&d, Dialog::SaveChanges { .. }) {
        // Intercept touches behind the dialog; this must not block the buttons.
        egui::Area::new(egui::Id::new("wordcraft.unsaved.modal.backdrop"))
            .order(egui::Order::Foreground)
            .fixed_pos(egui::Pos2::ZERO)
            .interactable(true)
            .show(ctx, |ui| {
                let rect = ctx.content_rect();
                ui.allocate_rect(rect, egui::Sense::click_and_drag());
                ui.painter().rect_filled(rect, 0.0, egui::Color32::from_black_alpha(100));
            });
    }
'''
    foreground_window = WINDOW.replace(
        '.collapsible(false).resizable(false)',
        '.collapsible(false).resizable(false).order(egui::Order::Foreground)',
    )
    next_chrome = once(original_chrome, WINDOW, modal + foreground_window, "modal backdrop")

    # Only write after every upstream anchor has been validated.
    dispatch.write_text(next_dispatch, encoding="utf-8")
    chrome.write_text(next_chrome, encoding="utf-8")
    print("Applied WordCraft v0.14.0 D/C/S and touch-blocking modal overlay")
