#!/usr/bin/env python3
"""Stage the v0.15.0 GridCraft Android Tools menu and reloadable font UI.

Runs ONLY on an isolated checkout of the exact official v0.15.0 sources.
Fail closed before writing any files if any expected API anchor changed.
This does NOT install the Android launcher, SAF services, dialog or keyboard ports.
"""
import argparse
from pathlib import Path
import hashlib
import shutil
import runpy
import tomllib

EXPECTED_VERSION = "0.15.0"
MARKER = "GRIDCRAFT_ANDROID_V0150_UI_PORT_V1"
MENU_MARKER = "GRIDCRAFT_ANDROID_NATIVE_MENU_V1"
ADDONS = Path(__file__).resolve().parent / "android_addons"
FILES = {
    "title": "crates/ui-egui/src/ribbon/title_bar.rs",
    "home": "crates/ui-egui/src/ribbon/home.rs",
    "fonts": "crates/ui-egui/src/fonts.rs",
    "lib": "crates/ui-egui/src/lib.rs",
    "app": "crates/ui-egui/src/app.rs",
    "app_fonts": "crates/ui-egui/src/app/fonts.rs",
}


def once(value: str, old: str, new: str, location: str) -> str:
    count = value.count(old)
    if count != 1:
        raise RuntimeError(f"{location}: expected exactly one anchor, found {count}: {old[:110]!r}")
    return value.replace(old, new, 1)


def stage(root: Path, *, verify_only: bool = False) -> dict:
    root = Path(root).resolve()
    manifest_path = root / "Cargo.toml"
    if not manifest_path.is_file():
        raise RuntimeError("Expected a separate official GridCraft source checkout")
    version = tomllib.loads(manifest_path.read_text())["workspace"]["package"]["version"]
    if version != EXPECTED_VERSION:
        raise RuntimeError(f"Refusing to patch upstream GridCraft {version}; expected {EXPECTED_VERSION}")
    sources = {}
    for key, relative in FILES.items():
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"Missing v0.15.0 GridCraft source: {relative}")
        sources[key] = path.read_text()
        if MARKER in sources[key] or (key == "title" and MENU_MARKER in sources[key]):
            raise RuntimeError(f"{relative}: already ported; refusing a duplicate application")

    # Owner-provided Gc mark, downsampled for Android native UI and launcher.
    # The same source PNG is used by the APK's adaptive icon pipeline.
    approved_icon = Path(__file__).resolve().parents[2] / "assets/gridcraft/launcher-user-20261103.png"
    icon_bytes = approved_icon.read_bytes()
    if not icon_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Approved Gc icon isn't a valid PNG")
    if hashlib.sha256(icon_bytes).hexdigest() != "e35af23c45ee75e1e026374c7b2458ac9f616cc82ffe39465f9c0ad3f3aeb7b2":
        raise RuntimeError("Approved GridCraft Gc PNG changed: re-review launcher asset")
    menu = (ADDONS / "GridCraftNativeMenu.rs.inc").read_text()
    if menu.count(MENU_MARKER) != 1 or 'ui.menu_button("GridCraft Tools"' not in menu:
        raise RuntimeError("Approved GridCraft native Tools menu changed unexpectedly")
    # Same menu contents, but anchored directly BELOW the top-left clickable Gc
    # Button::new(Image) works on egui 0.37; no extra toolbar row.
    menu = menu.replace(
        'ui.menu_button("GridCraft Tools", |ui| {',
        'egui::Popup::menu(&gc_button).show(|ui| {', 1,
    )
    title_anchor = '            let more = icon_button(ui, Icon::More, t.text_dim, "More commands", vec2(26.0, ch));'
    # Decode once via the already-present 'image' crate, then cache a real GPU
    # texture. egui::include_image! requires a loader that Android doesn't
    # register; that produced the user's red broken-image warning triangle.
    icon_ui = """            ui.add_space(TITLE_LEFT_PAD);
            // GRIDCRAFT_ANDROID_USER_ICON_V2: exact supplied Gc design; no broken-image loader.
            let gc_texture_key = egui::Id::new("gridcraft.android.gc.texture");
            let gc_texture = match ui.ctx().data(|d| d.get_temp::<egui::TextureHandle>(gc_texture_key)) {
                Some(texture) => texture,
                None => {
                    let image = image::load_from_memory(include_bytes!("gridcraft-approved-mark.png"))
                        .expect("approved Gc icon PNG").into_rgba8();
                    let [width, height] = [image.width() as usize, image.height() as usize];
                    let pixels = egui::ColorImage::from_rgba_unmultiplied([width, height], image.as_raw());
                    let texture = ui.ctx().load_texture(
                        "gridcraft-gc-icon", pixels, egui::TextureOptions::LINEAR,
                    );
                    ui.ctx().data_mut(|d| d.insert_temp(gc_texture_key, texture.clone()));
                    texture
                }
            };
            // egui 0.37 removed ImageButton: Button::new(Image) retains the
            // exact 26px GPU texture without the auto font-height shrink of
            // Button::image. Popup::menu anchors directly beneath this response.
            let gc_button = ui.add(egui::Button::new(
                egui::Image::from_texture((gc_texture.id(), vec2(26.0, ch)))
            ).frame(false)).on_hover_text("GridCraft Tools");
            ui.add_space(5.0);
"""
    sources["title"] = once(
        sources["title"],
        "            ui.add_space(TITLE_LEFT_PAD);",
        icon_ui.rstrip(),
        FILES["title"],
    )
    sources["title"] = once(
        sources["title"], title_anchor,
        "            // " + MARKER + ": Android Tools menu in relocated title_bar.rs\n"
        + menu + title_anchor, FILES["title"],
    )
    old_combo = '    let items: Vec<(&str, String)> = FONTS.iter().map(|f| (*f, f.to_string())).collect();'
    new_combo = (
        "    // " + MARKER + ": include imported/system catalog families, not only static names.\n"
        "    let available = crate::fonts::families();\n"
        "    let items: Vec<(&str, String)> = available.iter()\n"
        "        .map(|name| (name.as_str(), name.clone())).collect();"
    )
    sources["home"] = once(sources["home"], old_combo, new_combo, FILES["home"])

    home_anchor = '                dirs.push(h.join(".local/share/fonts"));'
    home_patch = (
        home_anchor + "\n"
        "                // " + MARKER + ": Android private HOME contains imported/shared font caches.\n"
        '                dirs.push(h.join("ArtCraft-Fonts/artcraft-imported"));\n'
        '                dirs.push(h.join("ArtCraft-Fonts/artcraft-shared"));'
    )
    sources["fonts"] = once(sources["fonts"], home_anchor, home_patch, FILES["fonts"])
    fontpatch = runpy.run_path(str(ADDONS / "font_catalog_patch.py"))
    sources["fonts"] = fontpatch["patch_catalog"](sources["fonts"])

    sources["lib"] = once(
        sources["lib"], "    fonts_seen: (u64, u64),",
        "    fonts_seen: (u64, u64),\n"
        "    // " + MARKER + ": reload trigger for newly imported fonts.\n"
        "    android_font_generation: u64,", FILES["lib"],
    )
    sources["app"] = once(
        sources["app"], "            fonts_seen: (0, 0),",
        "            fonts_seen: (0, 0),\n            android_font_generation: 0,",
        FILES["app"],
    )
    sources["app_fonts"] = once(
        sources["app_fonts"],
        "        let seen = self.fonts_key();\n        if seen == self.fonts_seen {\n            return;\n        }",
        "        // " + MARKER + ": importing fonts triggers a fresh font binding even if the workbook did not change.\n"
        "        let generation = fonts::generation();\n"
        "        let catalog_changed = generation != self.android_font_generation;\n"
        "        self.android_font_generation = generation;\n"
        "        let seen = self.fonts_key();\n"
        "        if !catalog_changed && seen == self.fonts_seen {\n            return;\n        }",
        FILES["app_fonts"],
    )
    sources["app_fonts"] = once(
        sources["app_fonts"], "        if used == self.fonts_bound {",
        "        if !catalog_changed && used == self.fonts_bound {", FILES["app_fonts"],
    )
    expected = {
        "title": MENU_MARKER,
        "home": "let available = crate::fonts::families();",
        "fonts": "pub fn reload_catalog()",
        "lib": "android_font_generation: u64",
        "app": "android_font_generation: 0",
        "app_fonts": "catalog_changed",
    }
    if sources["title"].count("GRIDCRAFT_ANDROID_USER_ICON_V2") != 1 or "gridcraft-approved-mark.png" not in sources["title"] or 'egui::Popup::menu(&gc_button)' not in sources["title"] or 'egui::Button::new(' not in sources["title"] or 'egui::ImageButton' in sources["title"] or 'ui.menu_button("GridCraft Tools"' in sources["title"]:
        raise RuntimeError("Owner approved GridCraft title-bar icon was not included")
    for key, value in expected.items():
        if value not in sources[key]:
            raise RuntimeError(f"{FILES[key]}: expected ported code not found")
    # Commit all six files only when every anchor and invariance check succeeded.
    if not verify_only:
        for key, relative in FILES.items():
            (root / relative).write_text(sources[key])
        shutil.copyfile(approved_icon, root / "crates/ui-egui/src/ribbon/gridcraft-approved-mark.png")
    return {
        "source_version": version,
        "files_verified": sorted(FILES.values()),
        "android_menu_staged": True,
        "font_dropdown_staged": True,
        "reloadable_font_catalog_staged": True,
        "workspace_modified": not verify_only,
        "launcher_port_complete": False,
        "android_apk_compiled": False,
    }


def main():
    import json
    p = argparse.ArgumentParser()
    p.add_argument("upstream_checkout", type=Path)
    p.add_argument("--verify-only", action="store_true", help="Validate transformations without writing to checkout")
    args = p.parse_args()
    print(json.dumps(stage(args.upstream_checkout, verify_only=args.verify_only), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
