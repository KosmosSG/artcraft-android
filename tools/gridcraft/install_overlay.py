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
    if not ribbon.is_file():
        raise RuntimeError("Pinned GridCraft UI ribbon not found")
    ribbon_source = ribbon.read_text()
    menu_anchor = '            let more = icon_button(ui, Icon::More, t.text_dim, "More commands", vec2(26.0, ch));'
    menu_marker = "GRIDCRAFT_ANDROID_NATIVE_MENU_V1"
    if ribbon_source.count(menu_anchor) != 1 or menu_marker in ribbon_source:
        raise RuntimeError("Pinned GridCraft title bar changed or menu already inserted; manual review needed")
    native_menu = (additions / "GridCraftNativeMenu.rs.inc").read_text()
    if native_menu.count(menu_marker) != 1 or 'ui.menu_button("GridCraft Tools"' not in native_menu:
        raise RuntimeError("GridCraft top menu contract missing")
    patched_ribbon = ribbon_source.replace(menu_anchor, native_menu + menu_anchor, 1)
    # Other projects, signing keys, upstream releases and publisher untouched.
    ribbon.write_text(patched_ribbon)
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
