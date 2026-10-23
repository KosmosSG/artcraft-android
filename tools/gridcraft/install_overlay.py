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
    for file in ("overlay.py", "gridcraft_tools.rs", "GridCraftJavaMethods.java.inc"):
        if not (additions / file).is_file():
            raise RuntimeError(f"Missing reviewed enhancement source {file}")
    dest = builder / "tools/gridcraft_android"
    if dest.exists():
        raise RuntimeError("A GridCraft overlay directory already exists; refusing overwrite")
    # Do not touch source/<app>, keys, other app adapters or .github workflows.
    dest.mkdir(parents=True)
    for item in ("overlay.py", "gridcraft_tools.rs", "GridCraftJavaMethods.java.inc"):
        shutil.copyfile(additions / item, dest / item)
    # All generated files (Cargo.toml, Java Activity, Rust lib.rs) must exist first.
    # Inject immediately AFTER the generator writes lib.rs, before its
    # atomic staging-directory rename publishes the Android launcher.
    source.write_text(text.replace(TRIGGER, TRIGGER + "\n" + SNIPPET, 1))
    print("Installed isolated GridCraft source overlay in disposable builder checkout.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path, help="Disposable builder checkout, e.g. ./builder")
    opts = parser.parse_args()
    install(opts.builder, Path(__file__).resolve().parent / "android_addons")
