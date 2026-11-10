#!/usr/bin/env python3
"""Exercise real legacy Android source patch functions on an isolated v0.19 checkout.

Does not modify tracked code or claim a production-ready Android integration.
CI should use a disposable, independently cloned upstream checkout.
"""
from pathlib import Path
import json
import sys

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: dry_run_v019_source_port.py ISOLATED_OFFICIAL_V019_CHECKOUT")
    source = Path(sys.argv[1]).resolve()
    if source.name == "designcraft" and source.parent.name == "source":
        raise SystemExit("Refusing to patch a builder's persistent source/designcraft checkout")
    if not (source / ".git").exists():
        raise SystemExit("Expected independently cloned upstream Git checkout")
    from audit_v019_compatibility import audit
    repo = Path(__file__).resolve().parents[2]
    checks = audit(source, repo)
    if not all(c["ok"] for c in checks):
        raise SystemExit("Source audit failed; patch attempt prohibited")
    from patch_v017_android import patch_source
    from patch_v017_interactions import ui_source
    stages = []
    try:
        patch_source(source)
        stages.append("legacy-v017-android-upstream-patch")
        ui_source(source)
        stages.append("legacy-v017-menu-and-input-patch")
    except Exception as exc:
        print(json.dumps({"result": "blocked", "stages": stages, "error": str(exc)}, indent=2))
        raise
    expected = {
        "crates/ui-egui/src/cursors.rs": 'target_os = "android"',
        "crates/ui-egui/src/menus/ui_commands.rs": "app.artcraftSelectSharedFonts",
        "crates/ui-egui/src/chrome/app_bar.rs": "dc_launcher_menu",
        "crates/fonts/src/fontdb/system.rs": "/product/fonts",
        "crates/ui-egui/src/dialogs.rs": "designcraft.unsaved.dcs",
    }
    for file, needle in expected.items():
        if needle not in (source / file).read_text():
            raise RuntimeError(f"Missing required feature after patch: {file}: {needle}")
    print(json.dumps({"result": "source-patches-applied-in-temporary-checkout", "stages": stages, "features_checked": list(expected)}, indent=2))
    print("Launcher and Java overlays, Cargo build, APK signature and physical testing remain unverified.")

if __name__ == "__main__":
    main()
