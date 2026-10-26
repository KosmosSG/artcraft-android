#!/usr/bin/env python3
"""Rebase the *existing* Android menu hooks onto an exact v0.14.0 source checkout.

Only called on the disposable, SHA-verified official checkout; never patches
builder sources or silently drops PhotoCraft Android menu features.
"""
from pathlib import Path
import sys

IDS = (
    "window.artcraftCustomFonts",
    "window.artcraftFontCatalog",
    "window.artcraftSharedFontsSelect",
    "window.artcraftSharedFontsRefresh",
    "window.artcraftTouchShortcutPad",
    "help.artcraftUpdateSettings",
    "help.artcraftCheckUpdates",
)

def unique_replace(text: str, before: str, after: str) -> str:
    n = text.count(before)
    if n != 1:
        raise RuntimeError(f"PhotoCraft v0.14 menu API needs manual review (anchor count {n}): {before[:100]!r}")
    return text.replace(before, after, 1)

def rebase(text: str) -> str:
    if any(s in text for s in IDS):
        raise RuntimeError("Refusing to rebase an already modified upstream menu")
    text = unique_replace(
        text,
        "/// Top-level menus in Photoshop order.\n",
        '''// Existing PhotoCraft Android commands; never add these to desktop menus.
#[cfg(target_os = "android")]
pub fn artcraft_shortcut_pad_allowed(app: &PhotocraftApp, id: &str) -> bool {
    modal_allows(app, id) && is_enabled(app, id)
}

#[cfg(target_os = "android")]
pub fn artcraft_shortcut_pad_chrome_hidden(app: &PhotocraftApp) -> bool {
    app.ui.view.hides_chrome()
}

// Match VectorCraft's guarded direct Type exit, using PhotoCraft's own
// commit/cancel semantics and preference. Never remap printable shortcuts.
#[cfg(target_os = "android")]
pub fn artcraft_type_escape_requested(app: &PhotocraftApp, ctx: &egui::Context, raw: &egui::RawInput) -> bool {
    if app.ui.text_edit.is_none() { return false; }
    if ctx.text_edit_focused()
        || !app.ui.dialogs.is_empty() || app.discard.is_some()
        || crate::type_transform::active(app)
        || crate::menu_nav::is_open(ctx) || crate::menu_keys::is_focused(ctx)
        || crate::widgets::dropdown_list_open(ctx)
        || app.ui.canvas_tool_menu.is_some()
    { return false; }
    let escape = |e: &egui::Event| matches!(e,
        egui::Event::Key { key: egui::Key::Escape, pressed: true, repeat: false, modifiers, .. }
        if !modifiers.any());
    raw.events.iter().any(escape)
}

// Run AFTER upstream logic has applied this frame's text/IME events. Preedit is
// already stored in the text layer; native commit preserves it just as clicking
// outside the layer does. Never discard an Escape because text shared its frame.
#[cfg(target_os = "android")]
pub fn artcraft_finish_type_escape(app: &mut PhotocraftApp) -> bool {
    let Some(edit) = app.ui.text_edit.as_ref() else { return false };
    if edit.mask || !app.session.prefs().type_.use_esc_to_commit {
        crate::type_tool::cancel(app);
    } else {
        crate::type_tool::commit(app);
    }
    if app.ui.text_edit.is_some() { return false; }
    true
}

#[cfg(target_os = "android")]
pub fn artcraft_escape_state(app: &PhotocraftApp, ctx: &egui::Context) -> String {
    format!("At Esc: field={} keyboard={} inline={} dialogs={} discard={} transform={} menu={} menukeys={} dropdown={} toolmenu={}",
        ctx.text_edit_focused(), ctx.egui_wants_keyboard_input(), app.ui.text_edit.is_some(),
        app.ui.dialogs.len(), app.discard.is_some(), crate::type_transform::active(app),
        crate::menu_nav::is_open(ctx), crate::menu_keys::is_focused(ctx),
        crate::widgets::dropdown_list_open(ctx), app.ui.canvas_tool_menu.is_some())
}

const CUSTOM_FONTS_ID: &str = "window.artcraftCustomFonts";
const FONT_CATALOG_ID: &str = "window.artcraftFontCatalog";
const SHARED_SELECT_ID: &str = "window.artcraftSharedFontsSelect";
const SHARED_REFRESH_ID: &str = "window.artcraftSharedFontsRefresh";
const SHORTCUT_PAD_ID: &str = "window.artcraftTouchShortcutPad";
const UPDATE_SETTINGS_ID: &str = "help.artcraftUpdateSettings";
const CHECK_UPDATES_ID: &str = "help.artcraftCheckUpdates";

/// Top-level menus in Photoshop order.
''',
    )
    text = unique_replace(
        text,
        "    let r = invoke_unguarded(app, ctx, id, params)?;",
        '''    #[cfg(target_os = "android")]
    {
        if id == SHORTCUT_PAD_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.shortcut_pad_toggle"), true));
            ctx.request_repaint();
            return Ok(Value::Null);
        }
        if id == CUSTOM_FONTS_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.custom_fonts_visible"), true));
            ctx.request_repaint();
            return Ok(Value::Null);
        }
        if id == FONT_CATALOG_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.font_catalog"), true));
            ctx.request_repaint();
            return Ok(Value::Null);
        }
        if matches!(id, SHARED_SELECT_ID | SHARED_REFRESH_ID | UPDATE_SETTINGS_ID) {
            let key = match id {
                SHARED_SELECT_ID => "artcraft.shared_fonts_select",
                SHARED_REFRESH_ID => "artcraft.shared_fonts_refresh",
                _ => "artcraft.update_settings",
            };
            ctx.data_mut(|d| d.insert_temp(egui::Id::new(key), true));
            ctx.request_repaint();
            return Ok(Value::Null);
        }
        if id == CHECK_UPDATES_ID {
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.check_updates_requested"), true));
            ctx.request_repaint();
            return Ok(Value::Null);
        }
    }
    let r = invoke_unguarded(app, ctx, id, params)?;''',
    )
    text = unique_replace(
        text,
        "pub fn is_enabled(app: &PhotocraftApp, id: &str) -> bool {\n",
        '''pub fn is_enabled(app: &PhotocraftApp, id: &str) -> bool {
    #[cfg(target_os = "android")]
    if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID) {
        return true;
    }
''',
    )
    text = unique_replace(
        text,
        "pub fn is_live(id: &str) -> bool {\n",
        '''pub fn is_live(id: &str) -> bool {
    #[cfg(target_os = "android")]
    if matches!(id, CUSTOM_FONTS_ID | FONT_CATALOG_ID | SHARED_SELECT_ID | SHARED_REFRESH_ID |
                     SHORTCUT_PAD_ID | UPDATE_SETTINGS_ID | CHECK_UPDATES_ID) {
        return true;
    }
''',
    )
    text = unique_replace(
        text,
        "    crate::plugin_ui::insert_menu_items(app, &mut items);",
        '''    #[cfg(target_os = "android")]
    {
        for (id, label, menu) in [
            (CUSTOM_FONTS_ID, "Import Font…", "Type"),
            (FONT_CATALOG_ID, "Detected Fonts…", "Type"),
            (SHARED_SELECT_ID, "Select Shared Font Folder…", "Type"),
            (SHARED_REFRESH_ID, "Refresh Shared Fonts", "Type"),
            (SHORTCUT_PAD_ID, "Touch Shortcut Pad", "Window"),
            (UPDATE_SETTINGS_ID, "Update Settings…", "Help"),
            (CHECK_UPDATES_ID, "Check for Updates", "Help"),
        ] {
            let entry = MenuItem {
                id: id.into(), label: label.into(), path: vec![menu.into()],
                shortcut: None, enabled: true, checked: None, color: None,
            };
            let at = items.iter().rposition(|i| i.path.first().map(String::as_str) == Some(menu))
                .map_or(items.len(), |p| p + 1);
            items.insert(at, entry);
        }
    }
    crate::plugin_ui::insert_menu_items(app, &mut items);''',
    )
    if not all(text.count(value) >= 1 for value in IDS):
        raise RuntimeError("Some Android menu commands were lost during port")
    return text

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: photocraft_v014_menu_port.py PATH_TO_PINNED_UPSTREAM_MENUS")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    updated = rebase(text)
    path.write_text(updated, encoding="utf-8")
    print("PASS: original PhotoCraft Android menu actions and detected-font diagnostics staged in v0.14 source")

if __name__ == "__main__":
    main()
