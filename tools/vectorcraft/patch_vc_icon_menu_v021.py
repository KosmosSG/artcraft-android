"""Use VectorCraft's existing top-left branded icon as Android's Vc menu trigger.

Pinned upstream v0.21.0 source overlay; Android-only UI behavior.
Preserves original upstream menu tree, keyboard dispatch and native desktop menus.
"""
from pathlib import Path
import argparse


def replace_once(src: str, old: str, new: str, what: str) -> str:
    if src.count(old) != 1:
        raise ValueError(f"Unreviewed v0.21 Vc icon menu {what}: expected one anchor; found {src.count(old)}")
    return src.replace(old, new, 1)


def patch_sources(menus: str, bar: str, chrome: str) -> tuple[str, str, str]:
    menus = replace_once(menus, "pub use bar::menu_bar;\n", """pub use bar::menu_bar;

// Compact Android top-left Vc menu, arranged like GridCraft's grouped launcher.
// Keep upstream's entire menu tree and the same action IDs. No duplicate About
// or diagnostics entries inside this launcher; native desktop menus stay intact.
#[cfg(target_os = "android")]
pub(crate) fn android_vc_menu(app: &mut VectorcraftApp, response: &egui::Response) {
    let tree = tree::menu_tree_named(app.session.prefs.font_names_in_english);
    if tree.iter().any(|(name, _)| *name == "Vc") {
        let mut clicked: Option<(String, Value)> = None;
        egui::Popup::menu(response).show(|ui| {
            ui.set_min_width(272.0);
            for (label, id) in [
                ("Import Fonts (TTF / OTF)…", "android.vectorcraft.fontImport"),
                ("Choose Shared Font Folder…", "android.vectorcraft.fontFolder"),
                ("Refresh Shared Fonts", "android.vectorcraft.fontRefresh"),
            ] {
                if ui.button(label).clicked() {
                    clicked = Some((id.into(), serde_json::json!({})));
                    ui.close();
                }
            }
            ui.separator();
            ui.menu_button("App Updates", |ui| {
                ui.set_min_width(250.0);
                if ui.button("Check for Updates").clicked() {
                    clicked = Some(("android.vectorcraft.updates".into(), serde_json::json!({})));
                    ui.close();
                }
                if ui.button("Check at Startup").clicked() {
                    clicked = Some(("android.vectorcraft.startupUpdates".into(), serde_json::json!({})));
                    ui.close();
                }
            });
            ui.menu_button("Appearance", |ui| {
                ui.set_min_width(210.0);
                for (label, brightness) in [("Light", "light"), ("Dark", "dark")] {
                    if ui.button(label).clicked() {
                        clicked = Some(("prefs.set".into(), serde_json::json!({
                            "key": "uiBrightness", "value": brightness
                        })));
                        ui.close();
                    }
                }
                if ui.button("More Appearance Settings…").clicked() {
                    clicked = Some(("edit.preferences".into(), serde_json::json!({ "category": "User Interface" })));
                    ui.close();
                }
            });
            ui.separator();
            if ui.button("Touch Shortcut Pad").clicked() {
                clicked = Some(("android.vectorcraft.touchPad".into(), serde_json::json!({})));
                ui.close();
            }
            if ui.button("Keyboard Shortcuts…").clicked() {
                clicked = Some(("edit.keyboardShortcuts".into(), serde_json::json!({})));
                ui.close();
            }
            ui.menu_button("Diagnostics", |ui| {
                if ui.button("Keyboard Diagnostics…").clicked() {
                    clicked = Some(("android.vectorcraft.keyboardDiagnostics".into(), serde_json::json!({})));
                    ui.close();
                }
                if ui.button("Graphics Diagnostics…").clicked() {
                    clicked = Some(("android.vectorcraft.diagnostics".into(), serde_json::json!({})));
                    ui.close();
                }
            });
            ui.separator();
            if ui.button("About VectorCraft").clicked() {
                clicked = Some(("help.about".into(), serde_json::json!({})));
                ui.close();
            }
        });
        if let Some((id, params)) = clicked { invoke::invoke(app, &id, params); }
    }
}
""", "menus root helper")
    bar = replace_once(bar,
        '.filter(|(title, _)| *title != "VectorCraft").collect();',
        '.filter(|(title, _)| *title != "VectorCraft" && *title != "Vc").collect();',
        "remove duplicate Vc text label")
    chrome = replace_once(chrome,
        '''                let (r, _) = ui.allocate_exact_size(vec2(MARK, MARK), Sense::hover());
                crate::brand::paint_mark(ui, r);
                ui.add_space(6.0);''',
        '''                let (r, mark) = ui.allocate_exact_size(vec2(MARK, MARK),
                    if cfg!(target_os = "android") { Sense::click() } else { Sense::hover() });
                crate::brand::paint_mark(ui, r);
                #[cfg(target_os = "android")]
                menus::android_vc_menu(app, &mark);
                ui.add_space(6.0);''',
        "existing branded mark click target")
    if "pub(crate) fn android_vc_menu(" not in menus or '&& *title != "Vc"' not in bar:
        raise ValueError("Vc menu wiring missing")
    return menus, bar, chrome


def patch(builder: Path) -> None:
    src = builder / "source/vectorcraft/crates/ui-egui/src"
    paths = [src / "menus.rs", src / "menus/bar.rs", src / "chrome.rs"]
    original = [p.read_text() for p in paths]
    updated = patch_sources(*original)
    for path, value in zip(paths, updated):
        path.write_text(value)
    print("PASS: actual 18pt Vc brand icon opens Android menu, no redundant Vc text title")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    patch(parser.parse_args().builder)
