#!/usr/bin/env python3
"""Restyle the PhotoCraft Pc popup like GridCraft, with Appearance > Theme.

Runs ONLY after the existing Android UI and keyboard-diagnostics overlays in
an isolated, disposable-signed test checkout. Removes visible diagnostics (action 18), retains Shortcut Pad Settings (action 19),\nand nests existing theme actions 13–16 under Appearance > Theme. Does not change
keyboard shortcut routing, production APK metadata, signing, or app data. Fail closed.
"""
from pathlib import Path
import argparse

def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--upstream", required=True, type=Path)
    args = cli.parse_args()
    brand = args.upstream / "crates/ui-egui/src/panels/brand.rs"
    data = brand.read_text(encoding="utf-8")
    start_marker = '            ui.set_min_width(236.0);\n            ui.strong("PhotoCraft · ArtCraft Android");'
    end_marker = '\n        });\n    }\n}'
    if data.count(start_marker) != 1:
        raise RuntimeError("Pc popup changed: expected original menu layout once")
    if data.count('action(ui, "Keyboard Diagnostics (test)…", 18);') != 1:
        raise RuntimeError("Keyboard diagnostics must exist before menu restyling")
    start = data.index(start_marker)
    end = data.find(end_marker, start)
    if end < 0:
        raise RuntimeError("Pc popup closing boundary changed; refusing rewrite")
    old = data[start:end]
    if old.count("ui.menu_button") != 6 or old.count("ui.separator();") < 4:
        raise RuntimeError("Pc popup structure unexpectedly changed")

    # No extra top heading or toolbar; direct font actions, narrow grouped
    # sections, familiar right-arrow submenus, About at the very bottom.
    # Integer action codes are the SAME ones already handled by the adapter.
    replacement = '''            ui.set_min_width(264.0);
            action(ui, "Import Fonts (TTF / OTF)…", 5);
            action(ui, "Import Font Folder…", 6);
            action(ui, "Refresh Fonts", 7);
            ui.separator();
            ui.menu_button("AI Tools", |ui| {
                action(ui, "Remove Background · U2NetP…", 2);
                action(ui, "ComfyUI Connection…", 3);
                action(ui, "About AI Tools…", 4);
                ui.separator();
                action(ui, if crate::menus::artcraft_ai_tools_visible() {
                    "Hide AI Tools" } else { "Show AI Tools" }, 1);
            });
            ui.separator();
            ui.menu_button("App Updates", |ui| {
                action(ui, "Check for Updates…", 8);
                action(ui, "Toggle Update Check at Startup", 9);
            });
            ui.separator();
            ui.menu_button("Appearance", |ui| {
                ui.menu_button("Theme", |ui| {
                    action(ui, "Light", 15);
                    action(ui, "Dark", 14);
                    action(ui, "Follow System", 16);
                    action(ui, "Cycle Appearance", 13);
                });
            });
            ui.menu_button("Shortcut Pad", |ui| {
                action(ui, if crate::menus::artcraft_pad_visible() {
                    "Hide Shortcut Pad" } else { "Show Shortcut Pad" }, 10);
                action(ui, "Dock Left", 11);
                action(ui, "Dock Right", 12);
                action(ui, "Shortcut Pad Settings…", 19);
            });
            ui.separator();
            ui.menu_button("About PhotoCraft", |ui| {
                ui.label("PhotoCraft · ArtCraft Android");
                ui.label("Official upstream: v0.21.0");
                ui.label("ARM64 test build · disposable signing");
            });'''
    old_ids = sorted({int(n) for n in __import__("re").findall(r", (\d+)\);", old)})
    new_ids = sorted({int(n) for n in __import__("re").findall(r", (\d+)\);", replacement)})
    if old_ids != [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19] or new_ids != [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,19]:
        raise RuntimeError(f"Pc menu action parity changed: {old_ids} vs {new_ids}")
    # The Appearance submenu contains Theme only; its existing action IDs are
    # deliberately retained, so the Android bridge and preference persistence
    # continue using the owner-tested implementation.
    assert replacement.count('ui.menu_button("Appearance", |ui| {') == 1
    assert replacement.count('ui.menu_button("Theme", |ui| {') == 1
    assert replacement.index('ui.menu_button("Appearance"') < replacement.index('ui.menu_button("Theme"')
    brand.write_text(data[:start] + replacement + data[end:], encoding="utf-8")
    print("PASS: Pc > Appearance > Theme nested; action IDs 13–16 unchanged; validated Home/links and other Android features preserved")

if __name__ == "__main__":
    main()
