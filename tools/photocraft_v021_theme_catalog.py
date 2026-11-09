#!/usr/bin/env python3
"""PhotoCraft Android.5: expose the full pinned 14-theme catalogue in Pc > Appearance.

Run after the validated Android.4 Pc layout and Android.3 Home/URL overlays, in
the disposable CI checkout only. Reuse existing theme command IDs and state;
do not change renderer, theme definitions, production adapter, or signing.
Reject unreviewed anchors rather than silently changing source.
"""
from pathlib import Path
import argparse

DARK = (
    ("Pro", "Pro", "pro"),
    ("Pro Medium Gray", "ProMedium", "proMedium"),
    ("Studio", "Studio", "studio"),
    ("Solarized", "SolarizedDark", "solarizedDark"),
    ("Adwaita", "AdwaitaDark", "adwaitaDark"),
    ("Breeze", "BreezeDark", "breezeDark"),
    ("Soft Dark", "SoftDark", "softDark"),
)
LIGHT = (
    ("Pro Light Gray", "ProLightGray", "proLightGray"),
    ("Pro Light", "ProLight", "proLight"),
    ("Studio Light", "StudioLight", "studioLight"),
    ("Classic", "Classic", "classic"),
    ("Adwaita", "Adwaita", "adwaita"),
    ("Breeze", "BreezeLight", "breezeLight"),
    ("Soft Light", "SoftLight", "softLight"),
)

OLD_MENU = '''            ui.menu_button("Appearance", |ui| {
                ui.menu_button("Theme", |ui| {
                    action(ui, "Light", 15);
                    action(ui, "Dark", 14);
                    action(ui, "Follow System", 16);
                    action(ui, "Cycle Appearance", 13);
                });
            });'''

ACTION_ANCHOR = '''        egui::Popup::menu(&response).show(|ui| {'''
ACTION_HELPER = '''        // The live theme comes from egui context, so ticks update after a
        // theme is selected without duplicating application preference state.
        let theme_action = |ui: &mut egui::Ui, title: &str,
                            kind: crate::theme::ThemeKind, code: u8| {
            let checked = crate::theme::Tokens::get(ui.ctx()).kind == kind;
            let label = if checked { format!("✓ {title}") }
                        else { format!("   {title}") };
            if ui.button(label).clicked() {
                crate::menus::artcraft_queue_pc_menu_action(code);
                ui.close();
            }
        };
'''

def once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one reviewed anchor, got {count}: {old[:70]!r}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", type=Path, required=True)
    ap.add_argument("--adapter", type=Path, required=True)
    args = ap.parse_args()

    brand = args.upstream / "crates/ui-egui/src/panels/brand.rs"
    host = args.adapter / "src/lib.rs"
    items = args.upstream / "crates/ui-egui/src/menus/items.rs"
    kinds = (args.upstream / "crates/ui-egui/src/theme.rs").read_text(encoding="utf-8")
    invoke = (args.upstream / "crates/ui-egui/src/menus/invoke.rs").read_text(encoding="utf-8")

    entries = DARK + LIGHT
    assert len(entries) == 14 and len({kind for _, kind, _ in entries}) == 14
    for _, kind, command in entries:
        if f"ThemeKind::{kind}" not in kinds or f'"window.theme.{command}"' not in invoke:
            raise RuntimeError(f"Missing official v0.21.0 ThemeKind/command mapping: {kind}/{command}")

    def menu_group(title: str, rows: tuple, first: int) -> str:
        group = f'                    ui.menu_button("{title}", |ui| {{\n'
        for code, (label, kind, _command) in enumerate(rows, first):
            group += f'                        theme_action(ui, "{label}", crate::theme::ThemeKind::{kind}, {code});\n'
        group += "                    });\n"
        return group

    menu = '''            ui.menu_button("Appearance", |ui| {
                ui.menu_button("Theme", |ui| {
''' + menu_group("Dark Theme", DARK, 20) + menu_group("Light Theme", LIGHT, 27) + '''                });
                action(ui, "Sync with System", 16);
                action(ui, "Next Appearance Mode", 13);
            });'''
    once(brand, ACTION_ANCHOR, ACTION_HELPER + ACTION_ANCHOR)
    once(brand, OLD_MENU, menu)

    # Codes 1–19 remain as in validated Android.4; action codes 20–33 route
    # through the same official Window › Theme invoke commands as desktop.
    command_cases = "\n".join(
        f'                    {code} => "window.theme.{command}",'
        for code, (_label, _kind, command) in enumerate(entries, 20)
    )
    dispatch = '''            20..=33 => {
                let command = match pc_action {
''' + command_cases + '''
                    _ => unreachable!("validated theme action range"),
                };
                if let Err(e) = photocraft_ui_egui::menus::invoke(
                    &mut self.inner, ui.ctx(), command, serde_json::json!({})
                ) { log::warn!("Theme selection: {e}"); }
            }
'''
    once(host, '            13..=16 => {', dispatch + '            13..=16 => {')

    # Hide duplicate theme entries from the Android Window UI only.
    # Their command definitions and keyboard/shortcut dispatch remain alive.
    # Desktop native menus and other platforms are entirely unaffected.
    marker = '    // Window: the open documents in tab order, after a separator, the active one checked.\n'
    hide = '''    // Android: all 14 themes live in Pc > Appearance > Theme; keep the
    // command IDs available for shortcut dispatch and deep links.
    #[cfg(target_os = "android")]
    items.retain(|item| {
        !(item.path.first().map(String::as_str) == Some("Window")
            && item.id.starts_with("window.theme."))
    });
'''
    once(items, marker, hide + marker)

    output = brand.read_text(encoding="utf-8")
    assert output.count('ui.menu_button("Dark Theme", |ui| {') == 1
    assert output.count('ui.menu_button("Light Theme", |ui| {') == 1
    assert output.count('action(ui, "Sync with System", 16);') == 1
    assert output.count('action(ui, "Next Appearance Mode", 13);') == 1
    for code in range(20, 34):
        assert output.count(f", {code});") == 1
    print("PASS: Pc > Appearance > Theme contains 14 live themes / selected ticks.")
    print("PASS: Sync with System and Next Appearance Mode are directly under Appearance.")
    print("PASS: duplicate Android Window theme entries hidden; command IDs preserved.")

if __name__ == "__main__":
    main()
