#!/usr/bin/env python3
"""FilmCraft v0.17 Android-only Fc icon menu and mouse-hover compatibility overlay.

Applied to a disposable checkout of the official v0.17.0 source. Never patches
the official upstream checkout in-place or another ArtCraft application.
"""
from __future__ import annotations
import argparse
from pathlib import Path

HOME_START = "    // Home\n"
HOME_END = "    // Mode tabs ("
HOVER_MENU_BUTTON = "            titles.push(r.response);"
HOVER_MENU_ENTRY = "    let r = ui.add_enabled(it.enabled, b);"
HOVER_SUBMENU = "            ui.menu_button(language.tr(sub), |ui| {"
HOVER_SUBMENU_END = "                menu_level(ui, &inner, depth + 1, clicked, auto, labels);\n            });"
MENU_STYLE_ANCHOR = "    egui::containers::menu::menu_style(s);"

ANDROID_HOME = '''    // Android replaces the Home glyph with the exact approved Fc icon.
    // The original Home navigation stays available inside the popup.
    let home = Rect::from_center_size(pos2(x + 10.0, rect.center().y), vec2(26.0, 26.0));
    let hresp = ui.interact(home, egui::Id::unique("hdr-home"), Sense::click());
    #[cfg(target_os = "android")]
    let hresp = hresp.on_hover_text("FilmCraft Android menu");
    #[cfg(not(target_os = "android"))]
    let hresp = hresp.on_hover_text(tl!("Home"));
    app.auto.add("header.home", home, "Home");
    if hresp.hovered() {
        p.rect_filled(home, 4.0, t.hover);
    }
    #[cfg(target_os = "android")]
    {
        crate::android_approved_brand::paint(&p, home.shrink(1.0));
        egui::Popup::menu(&hresp)
            .close_behavior(egui::PopupCloseBehavior::CloseOnClickOutside)
            .show(|ui| {
                ui.set_min_width(245.0);
                ui.label(egui::RichText::new("FilmCraft Android").strong());
                ui.separator();
                for (name, action) in [
                    ("Import Font…", 1u8),
                    ("Shared Font Folder…", 2u8),
                    ("Refresh Imported Fonts", 3u8),
                    ("Check for Updates…", 4u8),
                ] {
                    if ui.button(name).on_hover_cursor(egui::CursorIcon::PointingHand).clicked() {
                        ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("filmcraft.android.menu.action"), action));
                        ui.ctx().request_repaint();
                        ui.close();
                    }
                }
                let mut startup = ui.ctx().data(|d| d.get_temp::<bool>(
                    egui::Id::new("filmcraft.android.startup.enabled")).unwrap_or(false));
                if ui.checkbox(&mut startup, "Check for Updates at Startup")
                    .on_hover_cursor(egui::CursorIcon::PointingHand).changed()
                {
                    ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("filmcraft.android.menu.action"), 5u8));
                    ui.ctx().request_repaint();
                    ui.close();
                }
                ui.separator();
                if ui.button("Home / Import Workspace")
                    .on_hover_cursor(egui::CursorIcon::PointingHand).clicked()
                {
                    app.ui.mode = Mode::Import;
                    ui.close();
                }
            });
    }
    #[cfg(not(target_os = "android"))]
    {
        icons::paint(&p, home.shrink(5.0), Icon::Home, if hresp.hovered() { t.text } else { t.text_dim });
        if hresp.clicked() {
            app.ui.mode = Mode::Import;
        }
    }
    x = home.max.x + 16.0;
'''

MENU_STYLE = '''    egui::containers::menu::menu_style(s);
    #[cfg(target_os = "android")]
    {
        // A deliberate visible selected-row fill for MagicPad trackpad hover.
        // Scoped to native FilmCraft menus; touchscreen/timeline styles remain.
        let hovered = if s.visuals.dark_mode {
            egui::Color32::from_rgb(0x48, 0x52, 0x62)
        } else {
            egui::Color32::from_rgb(0xce, 0xde, 0xed)
        };
        s.visuals.widgets.hovered.bg_fill = hovered;
        s.visuals.widgets.hovered.weak_bg_fill = hovered;
        s.visuals.widgets.open.bg_fill = hovered;
        s.visuals.widgets.open.weak_bg_fill = hovered;
    }'''

def replace_once(source: str, anchor: str, replacement: str, description: str) -> str:
    n = source.count(anchor)
    if n != 1:
        raise RuntimeError(f"STOP: FilmCraft {description} changed: found {n} anchors")
    return source.replace(anchor, replacement, 1)

def patch_header(source: str) -> str:
    if source.count(HOME_START) != 1 or source.count(HOME_END) != 1:
        raise RuntimeError("STOP: FilmCraft v0.17 header Home anchors changed")
    start = source.index(HOME_START)
    end = source.index(HOME_END, start)
    old = source[start:end]
    for required in ('Icon::Home', '"hdr-home"', 'Mode::Import', 'x = home.max.x + 16.0;'):
        if required not in old:
            raise RuntimeError("STOP: approved Home/header behavior changed: " + required)
    return source[:start] + ANDROID_HOME + source[end:]

def patch_menus(source: str) -> str:
    source = replace_once(source, HOVER_MENU_BUTTON,
        "            titles.push(r.response.on_hover_cursor(egui::CursorIcon::PointingHand));",
        "top-level mouse hover")
    source = replace_once(source, HOVER_MENU_ENTRY,
        "    let r = ui.add_enabled(it.enabled, b).on_hover_cursor(egui::CursorIcon::PointingHand);",
        "menu entry hover cursor")
    source = replace_once(source, HOVER_SUBMENU,
        "            let _ = ui.menu_button(language.tr(sub), |ui| {", "submenu cursor start")
    source = replace_once(source, HOVER_SUBMENU_END,
        "                menu_level(ui, &inner, depth + 1, clicked, auto, labels);\n            }).response.on_hover_cursor(egui::CursorIcon::PointingHand);",
        "submenu cursor end")
    return source

def patch_theme(source: str) -> str:
    return replace_once(source, MENU_STYLE_ANCHOR, MENU_STYLE, "menu row contrast")

def stage(root: Path) -> None:
    root = root.resolve()
    if root.name != "filmcraft" or "filmcraft-builder" not in root.parts:
        raise RuntimeError("STOP: only disposable FilmCraft v0.17 checked-out source may be patched")
    src = root / "crates/ui-egui/src"
    paths = [src / "header.rs", src / "menus.rs", src / "theme.rs"]
    if not all(path.is_file() for path in paths):
        raise RuntimeError("STOP: incomplete upstream v0.17 UI source")
    original = [path.read_text() for path in paths]
    changed = [patch_header(original[0]), patch_menus(original[1]), patch_theme(original[2])]
    for path, content in zip(paths, changed):
        path.write_text(content)
    print("PASS: FilmCraft Fc icon menu, preserved Home, mouse hover feedback and hidden duplicate menus")

def self_test() -> None:
    sample = 'fn show() {\n' + HOME_START + \
        '    let hresp = ui.interact(home, egui::Id::unique("hdr-home"), Sense::click());\n' + \
        '    icons::paint(&p, home, Icon::Home, t.text);\n' + \
        '    app.ui.mode = Mode::Import;\n' + \
        '    x = home.max.x + 16.0;\n' + HOME_END + '\n}\n'
    result = patch_header(sample)
    assert 'crate::android_approved_brand::paint' in result
    assert 'egui::Popup::menu(&hresp)' in result
    assert 'filmcraft.android.menu.action' in result
    assert result.count('x = home.max.x + 16.0;') == 1
    assert '#[cfg(not(target_os = "android"))]' in result
    assert 'Mode::Import' in result
    assert 'filmcraft.android.startup.enabled' in result
    theme = patch_theme('pub fn menu_style(s: &mut egui::Style) {\n' + MENU_STYLE_ANCHOR + '\n}')
    assert 'widgets.hovered.weak_bg_fill' in theme
    try:
        patch_header(result)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Missing double-patch guard")
    print("PASS: FilmCraft icon menu Android guard, all five actions, Home fallback and hover style")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    options = parser.parse_args()
    if options.self_test:
        self_test()
    else:
        if options.source is None: parser.error("source is required")
        stage(options.source)

if __name__ == "__main__":
    main()
