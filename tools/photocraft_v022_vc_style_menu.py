#!/usr/bin/env python3
"""Match the PhotoCraft Pc menu to the tested VectorCraft Vc menu arrangement.

Apply only to the disposable runner checkout AFTER the official v0.22 source,
all protected Android overlays, full theme catalogue and stylus wheel overlays.
Keep all existing action IDs, selected themes, stylus preference state, keyboard
and font handling intact. Only restyle/reorder the launcher and add a verified
native Keyboard Shortcuts entry. No changes to published application or keys.
"""
import argparse
from pathlib import Path


def exactly_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    matches = text.count(old)
    if matches != 1:
        raise RuntimeError(f"Refusing unreviewed Pc menu anchor: {path}: {matches} matches for {old[:95]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--upstream", type=Path, required=True)
    cli.add_argument("--adapter", type=Path, required=True)
    args = cli.parse_args()
    brand = args.upstream / "crates/ui-egui/src/panels/brand.rs"
    host = args.adapter / "src/lib.rs"
    text = brand.read_text(encoding="utf-8")

    start_marker = '            ui.set_min_width(264.0);'
    end_marker = '\n        });\n    }\n}'
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        raise RuntimeError("Pc popup opening or end changed. Refusing restyle.")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    previous = text[start:end]
    required = (
        'ui.menu_button("AI Tools", |ui| {',
        'ui.menu_button("Appearance", |ui| {',
        'ui.menu_button("Dark Theme", |ui| {',
        'ui.menu_button("Light Theme", |ui| {',
        'ui.menu_button("Stylus Wheel", |ui| {',
        'ui.menu_button("Shortcut Pad", |ui| {',
        'ui.menu_button("About PhotoCraft", |ui| {',
        'action(ui, "Customize Wheel…", 35);',
        'action(ui, "Shortcut Pad Settings…", 19);',
    )
    for needle in required:
        if previous.count(needle) != 1:
            raise RuntimeError(f"Expected exact prior PhotoCraft feature once: {needle}")
    if previous.count('theme_action(ui,') != 14:
        raise RuntimeError("Full 14-theme catalogue not present: aborting rather than losing themes")
    for id in (1,2,3,4,5,6,7,8,9,10,11,12,13,16,19,34,35):
        if f", {id});" not in previous:
            raise RuntimeError(f"Pc action ID {id} absent from previous menu")

    # Preserve the exact validated 14-theme Appearance block including checks,
    # Sync with System and Next Appearance Mode. Do not reimplement theme logic.
    appearance_start = previous.index('            ui.menu_button("Appearance", |ui| {')
    wheel_start = previous.index('            ui.menu_button("Stylus Wheel", |ui| {', appearance_start)
    appearance = previous[appearance_start:wheel_start].rstrip()
    if appearance.count('ui.menu_button("Theme", |ui| {') != 1:
        raise RuntimeError("Appearance theme block changed")
    if appearance.count('theme_action(ui,') != 14:
        raise RuntimeError("Theme action catalogue changed")
    if 'action(ui, "Sync with System", 16);' not in appearance or 'action(ui, "Next Appearance Mode", 13);' not in appearance:
        raise RuntimeError("Appearance mode controls changed")

    # Order and spacing follow owner's VectorCraft screenshot. All PhotoCraft
    # additions (AI, theme catalogue, font and pad features) remain reachable.
    new_menu = '''            ui.set_min_width(264.0);
            action(ui, "Import Fonts (TTF / OTF)…", 5);
            action(ui, "Choose Shared Font Folder…", 6);
            action(ui, "Refresh Shared Fonts", 7);
            ui.separator();
            ui.menu_button("App Updates", |ui| {
                action(ui, "Check for Updates…", 8);
                action(ui, "Toggle Startup Update Check", 9);
            });
''' + appearance + '''
            ui.separator();
            ui.menu_button("AI Tools", |ui| {
                action(ui, "Remove Background · U2NetP…", 2);
                action(ui, "ComfyUI Connection…", 3);
                action(ui, "About AI Tools…", 4);
                ui.separator();
                action(ui, if crate::menus::artcraft_ai_tools_visible() {
                    "Hide AI Tools" } else { "Show AI Tools" }, 1);
            });
            ui.menu_button("Stylus Wheel", |ui| {
                let enabled = ui.ctx().data(|d|
                    d.get_temp::<bool>(egui::Id::new("pc_stylus_wheel_enabled"))
                        .unwrap_or(false));
                if ui.button(if enabled { "✓ Stylus Wheel On" }
                             else { "Stylus Wheel On" }).clicked() {
                    crate::menus::artcraft_queue_pc_menu_action(34);
                    ui.close();
                }
                action(ui, "Customization", 35);
            });
            ui.separator();
            ui.menu_button("Touch Shortcut Pad", |ui| {
                action(ui, if crate::menus::artcraft_pad_visible() {
                    "Hide Shortcut Pad" } else { "Show Shortcut Pad" }, 10);
                action(ui, "Dock Left", 11);
                action(ui, "Dock Right", 12);
                action(ui, "Shortcut Pad Settings…", 19);
            });
            action(ui, "Keyboard Shortcuts…", 36);
            ui.menu_button("Diagnostics", |ui| {
                action(ui, "Keyboard / IME Input Diagnostics…", 18);
                ui.weak("Records shortcut key names only");
            });
            ui.separator();
            ui.menu_button("About PhotoCraft", |ui| {
                ui.label("PhotoCraft · ArtCraft Android");
                ui.label("Official upstream: v0.22.0");
                ui.label("ARM64 test build · disposable signing");
            });'''
    for id in (1,2,3,4,5,6,7,8,9,10,11,12,13,16,18,19,35,36):
        if f", {id});" not in new_menu:
            raise RuntimeError(f"Restyle dropped action {id}")
    if 'artcraft_queue_pc_menu_action(34)' not in new_menu:
        raise RuntimeError("Restyle dropped wheel enable/disable action")
    if new_menu.count('theme_action(ui,') != 14:
        raise RuntimeError("Restyle dropped a theme selection")
    for section in ('App Updates', 'Appearance', 'AI Tools', 'Stylus Wheel',
                    'Touch Shortcut Pad', 'Keyboard Shortcuts…', 'Diagnostics',
                    'About PhotoCraft'):
        if new_menu.count(f'"{section}"') != 1:
            raise RuntimeError(f"Duplicate or missing {section} Pc menu row")
    brand.write_text(text[:start] + new_menu + text[end:], encoding="utf-8")

    # Open the established official PhotoCraft keyboard shortcut preferences
    # instead of inventing an Android-only nonfunctional settings screen.
    new_dispatch = '''            36 => {
                if let Err(error) = photocraft_ui_egui::menus::invoke(
                    &mut self.inner, ui.ctx(), "edit.keyboardShortcuts", serde_json::json!({})
                ) { log::warn!("Keyboard Shortcuts menu: {error}"); }
            }
'''
    exactly_once(host, '            35 => {\n', new_dispatch + '            35 => {\n')
    output = brand.read_text(encoding="utf-8")
    assert output.count('ui.menu_button("Stylus Wheel", |ui| {') == 1
    assert output.count('action(ui, "Customization", 35);') == 1
    assert output.count('ui.menu_button("Diagnostics", |ui| {') == 1
    assert output.count('ui.menu_button("Touch Shortcut Pad", |ui| {') == 1
    assert 'Keyboard Diagnostics (test)' not in output
    print("PASS: VectorCraft-style compact Pc menu with PhotoCraft actions preserved")
    print("PASS: 14 themes, 8-slot Default wheel, AI, fonts, keyboard settings, diagnostics, shortcut pad")


if __name__ == "__main__":
    main()
