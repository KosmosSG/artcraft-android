#!/usr/bin/env python3
"""Fail-closed compatibility helpers for an isolated EffectCraft v0.20.0 Android trial.

The released v0.16 Android line is unchanged. Never use these helpers to
overwrite an installed production APK or to sign/publish a release.
"""
from pathlib import Path

LEGACY_ANCHOR = "                        crate::widgets::menu_scroll(ui, |ui| menu_nodes(app, ui, children, &mut clicked, &mut nav, 0));"
MODERN_ANCHOR = "                        crate::widgets::menu_scroll(ui, browsing, |ui| menu_nodes(app, ui, children, &mut clicked, &mut nav, 0));"


def menu_path_and_anchor(upstream: Path) -> tuple[Path, str]:
    base = Path(upstream) / "crates/ui-egui/src"
    modern = base / "menus/bar.rs"
    legacy = base / "menus.rs"
    if modern.is_file():
        target, anchor = modern, MODERN_ANCHOR
    elif legacy.is_file():
        target, anchor = legacy, LEGACY_ANCHOR
    else:
        raise RuntimeError("STOP: EffectCraft menu sources missing (unsupported upstream)")
    source = target.read_text(encoding="utf-8")
    if source.count(anchor) != 1:
        raise RuntimeError("STOP: EffectCraft menu hook drift or duplicate; review upstream")
    if "artcraft.effectcraft.check_updates_requested" in source:
        raise RuntimeError("STOP: EffectCraft Android menu already injected")
    return target, anchor


def stage_trial_metadata(builder_root: Path) -> None:
    """Change metadata only in a throwaway builder checkout after prepare_candidate.py.

    Production 0.16.0-android.8 stays unmodified. The trial uses an independent
    package (set in the build command), temporary signer and TEST-only code.
    """
    path = Path(builder_root) / "lib/build-common.sh"
    data = path.read_text(encoding="utf-8")
    replacements = (
        ('version_line = f\'version = "{app_version}-android.3"\' if app == "effectcraft" else "version.workspace = true"',
         'version_line = f\'version = "{app_version}-android.1"\' if app == "effectcraft" else "version.workspace = true"'),
        ("version_code = 16781315", "version_code = 16810001"),
    )
    for old, new in replacements:
        if data.count(old) != 1 or new in data:
            raise RuntimeError("STOP: staged builder version source differs; refuse rewrite")
        data = data.replace(old, new, 1)
    path.write_text(data, encoding="utf-8")
