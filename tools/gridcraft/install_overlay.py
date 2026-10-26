#!/usr/bin/env python3
"""Install a GridCraft-only staging hook in an isolated builder checkout.

This is intentionally not a general change to the suite's main build script:
the GitHub candidate workflow checks out the pinned reference as ./builder,
then invokes this installer ONLY in that disposable workspace.
"""
import argparse
from pathlib import Path
import shutil

TRIGGER = '    (staging_dir / "src" / "lib.rs").write_text(entry)'
MARKER = 'GRIDCRAFT_OVERLAY_HOOK_V1'
SNIPPET = '''    # GRIDCRAFT_OVERLAY_HOOK_V1: GridCraft only, never other apps.
    if app == "gridcraft":
        import runpy
        runpy.run_path(str(root / "tools/gridcraft_android/overlay.py"),
                       init_globals={"staging_dir": staging_dir, "package_name": package_name, "root": root})
'''

def install(builder: Path, additions: Path):
    builder = builder.resolve()
    additions = additions.resolve()
    source = builder / "lib/build-common.sh"
    if not source.is_file() or not (builder / "build.sh").is_file():
        raise RuntimeError("Not an ArtCraft Android builder checkout")
    if builder == Path.cwd().resolve():
        raise RuntimeError("Refusing to modify the checked-out repository; provide a disposable builder directory")
    text = source.read_text()
    if MARKER in text:
        raise RuntimeError("Overlay hook already installed; refusing duplicate patch")
    if text.count(TRIGGER) != 1:
        raise RuntimeError("Builder generator changed; manual review needed before modifying it")
    required = ("if saf:", "GridCraftActivity", "mod ime_bridge;", "system_fonts::install_system_fonts(ui.ctx());")
    if any(item not in text for item in required):
        raise RuntimeError("Pinned builder lacks GridCraft SAF or font/keyboard infrastructure")
    for file in ("overlay.py", "gridcraft_tools.rs", "GridCraftJavaMethods.java.inc", "GridCraftNativeMenu.rs.inc"):
        if not (additions / file).is_file():
            raise RuntimeError(f"Missing reviewed enhancement source {file}")
    dest = builder / "tools/gridcraft_android"
    if dest.exists():
        raise RuntimeError("A GridCraft overlay directory already exists; refusing overwrite")
    # Patch only the pinned GridCraft checkout, never the suite or other apps.
    # Its existing title bar provides a native anchored menu; the generated
    # Android shell handles Java actions through egui Context data on next frame.
    ribbon = builder / "source/gridcraft/crates/ui-egui/src/ribbon.rs"
    native_menu = (additions / "GridCraftNativeMenu.rs.inc").read_text()
    menu_marker = "GRIDCRAFT_ANDROID_NATIVE_MENU_V1"
    if native_menu.count(menu_marker) != 1 or 'ui.menu_button("GridCraft Tools"' not in native_menu:
        raise RuntimeError("GridCraft top menu contract missing")
    # Read-only source audit downloads only the builder, not upstream sources.
    # In that limited audit checkout we still install the safe staging hook.
    # The real candidate build always checks out pinned GridCraft beforehand;
    # fail there if the ribbon is missing or its API changed.
    if ribbon.is_file():
        ribbon_source = ribbon.read_text()
        menu_anchor = '            let more = icon_button(ui, Icon::More, t.text_dim, "More commands", vec2(26.0, ch));'
        if ribbon_source.count(menu_anchor) != 1 or menu_marker in ribbon_source:
            raise RuntimeError("Pinned GridCraft title bar changed or menu already inserted; manual review needed")
        patched_ribbon = ribbon_source.replace(menu_anchor, native_menu + menu_anchor, 1)
        # GRIDCRAFT_ANDROID_FONT_COMBO_V1: the official GridCraft font scanner
        # already exposes families(), but this pinned v0.11.1 ribbon mistakenly
        # uses just the 17 built-in FONTS strings. Use the discovered catalog.
        combo_old = '    let items: Vec<(&str, String)> = FONTS.iter().map(|f| (*f, f.to_string())).collect();'
        combo_new = ('    // GRIDCRAFT_ANDROID_FONT_COMBO_V1: include scanned user-installed fonts.\n'
                     '    let available = crate::fonts::families();\n'
                     '    let items: Vec<(&str, String)> = available.iter()\n'
                     '        .map(|f| (f.as_str(), f.clone())).collect();')
        if patched_ribbon.count(combo_old) != 1 or "GRIDCRAFT_ANDROID_FONT_COMBO_V1" in patched_ribbon:
            raise RuntimeError("Pinned GridCraft font dropdown changed; manual review required")
        patched_ribbon = patched_ribbon.replace(combo_old, combo_new, 1)
        ribbon.write_text(patched_ribbon)
    elif (builder / "source/gridcraft").exists():
        raise RuntimeError("GridCraft checkout exists but the expected ribbon file is missing")
    # Official GridCraft's catalog scans its HOME fonts before the UI font
    # dropdown is populated (OnceLock). The system-font directory in HOME
    # is a symlink, so imported files must use a separate HOME folder.
    fonts = builder / "source/gridcraft/crates/ui-egui/src/fonts.rs"
    if fonts.is_file():
        scanned = fonts.read_text()
        home_font_anchor = '                dirs.push(h.join(".local/share/fonts"));'
        if scanned.count(home_font_anchor) != 1 or "GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1" in scanned:
            raise RuntimeError("GridCraft font catalog changed; manual review required")
        scanned = scanned.replace(
            home_font_anchor,
            home_font_anchor + '\n'
            + '                // GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1: Android internal HOME is shared with Java SAF.\n'
            + '                dirs.push(h.join("ArtCraft-Fonts/artcraft-imported"));\n                dirs.push(h.join("ArtCraft-Fonts/artcraft-shared"));',
            1
        )
        import runpy
        patch = runpy.run_path(str(additions / "font_catalog_patch.py"))
        scanned = patch["patch_catalog"](scanned)
        fonts.write_text(scanned)
        lib = fonts.with_name("lib.rs")
        lib.write_text(patch["patch_app"](lib.read_text()))
    elif (builder / "source/gridcraft").exists():
        raise RuntimeError("Pinned GridCraft font catalog missing")

    # GridCraft uses extracted lettering, not a scaled green square. The same
    # 66.56/108 foreground geometry as the pinned suite builder is retained.
    icon_script = builder / "lib/app_icons.py"
    icon_source = icon_script.read_text()
    icon_hook = '    foreground = _foreground(Image, stripped)'
    replacement = '''    # GRIDCRAFT_PADDED_ADAPTIVE_ICON_V3
    if app == "gridcraft":
        cutout = source.with_name("launcher-lettering.png")
        if not cutout.is_file():
            raise RuntimeError("GridCraft transparent lettering asset missing")
        lettering = Image.open(cutout).convert("RGBA")
        if lettering.getextrema()[3][0] != 0:
            raise RuntimeError("GridCraft lettering must have transparency")
        # Ignore nearly invisible extraction noise when measuring optical bounds.
        bounds = lettering.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
        if bounds is None:
            raise RuntimeError("GridCraft lettering is empty")
        lettering = lettering.crop(bounds)
        foreground = _foreground(Image, lettering)
        color = "#006039"
    else:
        foreground = _foreground(Image, stripped)'''
    if icon_source.count(icon_hook) != 1:
        raise RuntimeError("Pinned adaptive icon generator changed")
    icon_source = icon_source.replace(icon_hook, replacement, 1)
    # Match legacy surfaces to the adaptive visible 72dp area, without a second mask.
    legacy_hook = '    _write_legacy(source, pristine, res_dir)'
    legacy = '''    if app == "gridcraft":
        flat = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), color)
        flat.alpha_composite(foreground)
        inset = (CANVAS_PX - round(CANVAS_PX * 72 / 108)) // 2
        flat = flat.crop((inset, inset, CANVAS_PX - inset, CANVAS_PX - inset))
        for density, size in DENSITIES.items():
            out = res_dir / f"mipmap-{density}"
            out.mkdir(parents=True, exist_ok=True)
            flat.resize((size, size), Image.LANCZOS).save(out / "ic_launcher.png")
    else:
        _write_legacy(source, pristine, res_dir)'''
    if icon_source.count(legacy_hook) != 1:
        raise RuntimeError("Pinned legacy icon generator changed")
    icon_script.write_text(icon_source.replace(legacy_hook, legacy, 1))
    # Do not touch other source apps, keys, adapters or .github workflows.
    dest.mkdir(parents=True)
    for item in ("overlay.py", "gridcraft_tools.rs", "GridCraftJavaMethods.java.inc"):
        shutil.copyfile(additions / item, dest / item)
    # All generated files (Cargo.toml, Java Activity, Rust lib.rs) must exist first.
    # Inject immediately AFTER the generator writes lib.rs, before its
    # atomic staging-directory rename publishes the Android launcher.
    source.write_text(text.replace(TRIGGER, TRIGGER + "\n" + SNIPPET, 1))
    print("Installed isolated GridCraft native top Tools menu and Android source overlay.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path, help="Disposable builder checkout, e.g. ./builder")
    opts = parser.parse_args()
    install(opts.builder, Path(__file__).resolve().parent / "android_addons")
