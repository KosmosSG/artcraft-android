#!/usr/bin/env python3
"""Fail-closed FilmCraft Android File/Help bridge adapted to upstream v0.16.0.

Staged only in a disposable FilmCraft builder; upstream repository remains pristine.
The egui context carries an ephemeral u8 command to the Android wrapper's Java SAF
and GitHub updater bridge. No app-wide global state or new Android permissions.
"""
from __future__ import annotations

import argparse
from pathlib import Path

UPSTREAM_UPDATE_ENTRY = '    uic!("app.checkForUpdates", "Check for Updates…", ["Help"], None),'
COMMAND_ANCHOR = '    uic!("app.about", "About FilmCraft", ["Help"], None),'
INVOKE_ANCHOR = '    if id == "edit.selectAll" && ('
MENU_BAR_ANCHOR = '    let items = menu_items_with_focus(app, ui.ctx());'
COMMAND_INSERT = '''    // FilmCraft Android only: native File and Help commands, not a floating toolbar.
    #[cfg(target_os = "android")]
    uic!("android.filmcraft.importFont", "Import Font…", ["File"], None),
    #[cfg(target_os = "android")]
    uic!("android.filmcraft.sharedFonts", "Shared Font Folder…", ["File"], None),
    #[cfg(target_os = "android")]
    uic!("android.filmcraft.refreshFonts", "Refresh Imported Fonts", ["File"], None),
    #[cfg(target_os = "android")]

    #[cfg(target_os = "android")]
    uic!("android.filmcraft.startupUpdates", "Toggle Startup Update Checks", ["Help"], None),
    #[cfg(target_os = "android")]
    uic!("android.filmcraft.openRelease", "Open Available FilmCraft Release", ["Help"], None),
    #[cfg(target_os = "android")]
    uic!("android.filmcraft.buildInfo", "Android Build Info…", ["Help"], None),
'''
INVOKE_INSERT = '''    #[cfg(target_os = "android")]
    {
        let action: Option<u8> = match id {
            "android.filmcraft.importFont" => Some(1),
            "android.filmcraft.sharedFonts" => Some(2),
            "android.filmcraft.refreshFonts" => Some(3),
            "app.checkForUpdates" => Some(4),
            "android.filmcraft.startupUpdates" => Some(5),
            "android.filmcraft.openRelease" => Some(6),
            "android.filmcraft.buildInfo" => Some(7),
            _ => None,
        };
        if let Some(action) = action {
            ctx.data_mut(|data| {
                data.insert_temp(egui::Id::new("filmcraft.android.menu.action"), action);
            });
            app.ui.status = "FilmCraft Android: processing command…".to_owned();
            ctx.request_repaint();
            return Ok(Value::Null);
        }
    }
'''
MENU_BAR_INSERT = '''    #[cfg(target_os = "android")]
    if let Some(status) = ui.ctx().data_mut(|data| {
        let key = egui::Id::new("filmcraft.android.menu.status");
        let status = data.get_temp::<String>(key).filter(|s| !s.is_empty());
        if status.is_some() {
            data.insert_temp(key, String::new());
        }
        status
    }) {
        app.ui.status = status;
    }
'''


def once(s: str, anchor: str, replacement: str, label: str) -> str:
    n = s.count(anchor)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly one official v0.16.0 anchor, saw {n}")
    return s.replace(anchor, replacement, 1)


def patch(s: str) -> str:
    if '"android.filmcraft.importFont"' in s:
        raise RuntimeError("Native Android commands already staged; refuse double patch")
    # FilmCraft v0.16 already registers this one Help entry upstream.
    # Keep its label/position and redirect its action to the Android
    # release checker (action 4). Never add a visually duplicated entry.
    if s.count(UPSTREAM_UPDATE_ENTRY) != 1:
        raise RuntimeError("upstream Help > Check for Updates: expected exactly one entry")
    if 'uic!("android.filmcraft.checkUpdates"' in s:
        raise RuntimeError("obsolete duplicate Android Check for Updates entry")
    s = once(s, COMMAND_ANCHOR, COMMAND_INSERT + COMMAND_ANCHOR, "menu registration")
    s = once(s, INVOKE_ANCHOR, INVOKE_INSERT + INVOKE_ANCHOR, "menu dispatch")
    s = once(s, MENU_BAR_ANCHOR, MENU_BAR_INSERT + MENU_BAR_ANCHOR, "menu status")
    return s


def self_test() -> None:
    src = UPSTREAM_UPDATE_ENTRY + "\n" + COMMAND_ANCHOR + "\n" + INVOKE_ANCHOR + "\n" + MENU_BAR_ANCHOR + "\n"
    out = patch(src)
    assert all(f'android.filmcraft.{k}' in out for k in
               ("importFont", "sharedFonts", "refreshFonts",
                "startupUpdates", "openRelease", "buildInfo"))
    # Exactly one Help item, using the original upstream menu label/id.
    assert out.count(UPSTREAM_UPDATE_ENTRY) == 1
    assert out.count('"Check for Updates…"') == 1
    assert '"app.checkForUpdates" => Some(4),' in out
    assert '"android.filmcraft.checkUpdates"' not in out
    assert all(f'Some({i})' in out for i in range(1, 8))
    assert "filmcraft.android.menu.action" in out
    assert "filmcraft.android.menu.status" in out
    try:
        patch(out)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Missing double-patch guard")
    try:
        patch(COMMAND_ANCHOR + INVOKE_ANCHOR)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Missing drift guard")
    try:
        patch(src.replace(UPSTREAM_UPDATE_ENTRY, ""))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Missing upstream Check for Updates drift guard")
    try:
        patch(src.replace(UPSTREAM_UPDATE_ENTRY, UPSTREAM_UPDATE_ENTRY * 2))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Duplicated upstream Check for Updates must be rejected")
    print("PASS: FilmCraft one Help update entry; Android routes app.checkForUpdates to native action 4")



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.file:
        parser.error("Expected disposable official FilmCraft crates/ui-egui/src/menus.rs")
    target = args.file.resolve()
    if "filmcraft-builder" not in target.parts or target.parts[-4:] != (
            "crates", "ui-egui", "src", "menus.rs"):
        raise SystemExit("Refusing to patch outside the disposable FilmCraft source")
    original = target.read_text()
    modified = patch(original)
    target.write_text(modified)
    print("PASS: FilmCraft Android File/Help menu commands staged")


if __name__ == "__main__":
    main()
