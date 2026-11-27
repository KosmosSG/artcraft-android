#!/usr/bin/env python3
"""Fail-closed source-only compatibility probe for the DesignCraft v0.21.1 Android overlay.

Runs the exact legacy Android and interaction patch functions on an isolated clone.
It never touches the protected builder checkout, APK, signing keys, or release records.
"""
from pathlib import Path
import sys

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: dry_run_v0211_source_port.py ISOLATED_DESIGNCRAFT_CHECKOUT")
    source = Path(sys.argv[1]).resolve()
    if source.name != "designcraft" or not (source / ".git").exists():
        raise SystemExit("Expected an independently cloned official DesignCraft checkout named designcraft")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from patch_v017_android import patch_source
    from patch_v017_interactions import ui_source
    patch_source(source)
    ui_source(source)
    expected = {
        "crates/ui-egui/src/cursors.rs": 'target_os = "android"',
        "crates/ui-egui/src/menus/ui_commands.rs": "app.artcraftSelectSharedFonts",
        "crates/ui-egui/src/chrome/app_bar.rs": "dc_launcher_menu",
        "crates/fonts/src/fontdb/system.rs": "/product/fonts",
        "crates/ui-egui/src/dialogs.rs": "designcraft.unsaved.dcs",
    }
    for rel, needle in expected.items():
        path = source / rel
        if not path.is_file() or needle not in path.read_text():
            raise RuntimeError(f"Missing required Android feature after patch: {rel}: {needle}")
    print("PASS: DesignCraft v0.21.1 accepted the existing Android source and UI preservation overlays")
    print("Launcher, stylus wheel, native hover, Java bridge, APK packaging and device behavior remain separate gates.")

if __name__ == "__main__":
    main()
