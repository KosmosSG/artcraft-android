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

// Android puts the existing Vc menu beneath its existing branded mark,
// rather than adding a second text-labelled Vc button beside Home.
#[cfg(target_os = "android")]
pub(crate) fn android_vc_menu(app: &mut VectorcraftApp, response: &egui::Response) {
    let tree = tree::menu_tree_named(app.session.prefs.font_names_in_english);
    if let Some((_, items)) = tree.iter().find(|(name, _)| *name == "Vc") {
        let mut clicked: Option<(String, Value)> = None;
        egui::Popup::menu(response).show(|ui| bar::menu_body(app, ui, items, &mut clicked));
        if let Some((id, parameters)) = clicked {
            invoke::invoke(app, &id, parameters);
        }
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
