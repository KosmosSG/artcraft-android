#!/usr/bin/env python3
"""LightCraft v0.18-only Android compatibility patch.

Runs on checked-out COPIES of the exact upstream and reviewed Android builder.
Read-only by default (--check); --apply changes only local build checkouts.
The protected suite sources, other applications, releases and signing keys
are never rewritten. Fail closed on source drift.
"""
import argparse
import ast
import hashlib
import importlib.util
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
SUITE = HERE.parent.parent
UPSTREAM = "32d569ad5d19a6b55cf8d5c077127faa0f44a83b"
APP = "lightcraft"


def once(text: str, old: str, new: str, label: str) -> str:
    hits = text.count(old)
    if hits != 1:
        raise ValueError(f"STOP: LightCraft v0.18 {label}: expected 1 anchor; got {hits}")
    return text.replace(old, new, 1)


def legacy_payload(label: str) -> tuple[str, str]:
    """Extract the EXACT approved builder patch from the published Android baseline."""
    legacy = ast.parse((SUITE / "tools/lightcraft/apply_android_fixes.py").read_text())
    for node in ast.walk(legacy):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "replace_once":
            continue
        if len(node.args) == 4 and isinstance(node.args[3], ast.Constant) and node.args[3].value == label:
            a, b = node.args[1:3]
            if isinstance(a, ast.Constant) and isinstance(b, ast.Constant):
                return a.value, b.value
    raise ValueError(f"STOP: cannot find approved LightCraft patch: {label}")


def approved_updates_branch() -> str:
    """Re-use the published About/Updates tab rather than invent new UI semantics."""
    _, replacement = legacy_payload("native About dialog update controls")
    begin = "                        3 => {"
    end = "                        _ => {"
    if replacement.count(begin) != 1 or replacement.count(end) != 1:
        raise ValueError("STOP: approved Updates tab template drift")
    block = begin + replacement.split(begin, 1)[1].split(end, 1)[0]
    for anchor in ("channel_changed", "startup_changed", "check_updates_requested",
                   "installed_version", "open_release_requested"):
        if anchor not in block:
            raise ValueError(f"STOP: approved update control missing {anchor}")
    return block


def source_changes(source: Path) -> dict[Path, str]:
    paths = {
        "commands": source / "crates/ui-egui/src/menus/ui_commands.rs",
        "menubar": source / "crates/ui-egui/src/menus/menubar.rs",
        "run": source / "crates/ui-egui/src/menus/run.rs",
        "dialogs": source / "crates/ui-egui/src/dialogs.rs",
    }
    originals = {key: value.read_text(encoding="utf-8") for key, value in paths.items()}

    # Preserve upstream's existing Check for Updates menu ID, but route it to
    # the Android-specific Help -> About -> Updates tab on Android copies.
    c = originals["commands"]
    c = once(c,
        '    ("app.checkForUpdates", "Check for Updates…", None, "Help"),',
        '    ("app.checkForUpdates", "Check for Updates…", None, "Help"),\n'
        '    ("app.artcraftStartupUpdateSettings", "Startup Update Settings", None, "Help"),',
        "Help command registry")
    m = once(originals["menubar"],
        '            "app.checkForUpdates",\n            "app.about",',
        '            "app.checkForUpdates",\n            "app.artcraftStartupUpdateSettings",\n            "app.about",',
        "Help menu layout")
    run = originals["run"]
    handler = '''        "app.checkForUpdates" => {
            ctx.data_mut(|d| d.insert_temp(
                egui::Id::new("artcraft.lightcraft.check_updates_requested"), true));
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("about_tab"), 3u8));
            app.ui.dialog = Some(Dialog::About);
            ctx.request_repaint();
            Ok(Value::Null)
        }
        "app.artcraftStartupUpdateSettings" => {
            ctx.data_mut(|d| d.insert_temp(
                egui::Id::new("artcraft.lightcraft.startup_updates_requested"), true));
            ctx.data_mut(|d| d.insert_temp(egui::Id::new("about_tab"), 3u8));
            app.ui.dialog = Some(Dialog::About);
            ctx.request_repaint();
            Ok(Value::Null)
        },'''
    # Exact original is one match arm with a trailing comma.
    handler = handler.replace('        }\n        "app.artcraft', '        },\n        "app.artcraft', 1)
    run = once(run,
        '        "app.checkForUpdates" => crate::updates_ui::check(app),',
        handler,
        "check-updates command handler")

    dlg = originals["dialogs"]
    dlg = once(dlg,
        'pub const ABOUT_TABS: &[(&str, &str)] = &[("about", "About"), ("contributors", "Contributors"), ("models", "Models")];',
        'pub const ABOUT_TABS: &[(&str, &str)] = &[("about", "About"), ("contributors", "Contributors"), ("models", "Models"), ("updates", "Updates")];',
        "About tab registry")
    dlg = once(dlg,
        'let tab_id = egui::Id::unique("about_tab");',
        'let tab_id = egui::Id::new("about_tab");',
        "About tab shared selection ID")
    dlg = once(dlg,
        '        2 => crate::credits::models_ui(ui),\n        _ => {',
        '        2 => crate::credits::models_ui(ui),\n' + approved_updates_branch() + '        _ => {',
        "About Updates UI")
    return {paths["commands"]: c, paths["menubar"]: m, paths["run"]: run, paths["dialogs"]: dlg}


def builder_changes(builder: Path) -> dict[Path, str]:
    generator = builder / "lib/build-common.sh"
    icon_script = builder / "lib/app_icons.py"
    script = generator.read_text(encoding="utf-8")
    icon = icon_script.read_text(encoding="utf-8")
    old, new = legacy_payload("exact approved adaptive icon")
    icon = once(icon, old, new, "approved Lc adaptive launcher")
    ast.parse(icon)
    for name in ("Java Activity injection", "Rust updater host"):
        old, new = legacy_payload(name)
        script = once(script, old, new, name)
    # New builder already declares INTERNET: old permission patch would duplicate it.
    if script.count('name = "android.permission.INTERNET"') != 1:
        raise ValueError("STOP: Android builder INTERNET permission missing/duplicated")
    if script.count('    "lightcraft": {') != 1:
        raise ValueError("STOP: Android builder LightCraft SAF recipe drift")
    from patch_v017_builder import patch_source
    script = patch_source(script)
    for required in ("LIGHTCRAFT_V017_WRITE_NEW_PRIVATE_ONLY", "write_new: Some(Box::new("):
        if required not in script:
            raise ValueError(f"STOP: SAF create-new guard absent: {required}")
    return {generator: script, icon_script: icon}


def validate(source: Path, builder: Path, suite: Path) -> None:
    if source.resolve() == suite.resolve() or builder.resolve() == suite.resolve():
        raise ValueError("STOP: cannot patch protected suite repository")
    pinned_icon = suite / "assets/lightcraft/lc-user-approved.png"
    sha = hashlib.sha256(pinned_icon.read_bytes()).hexdigest()
    if sha != "8035dcf8bf966875ce4d51fec668581342cc774d69f3dacb977c94225dc997d4":
        raise ValueError("STOP: published Lc artwork has changed")
    if "0.18.0" not in (source / "Cargo.toml").read_text(encoding="utf-8"):
        raise ValueError("STOP: wrong upstream LightCraft version")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--builder", type=Path, required=True)
    p.add_argument("--suite", type=Path, default=SUITE)
    args = p.parse_args()
    validate(args.source, args.builder, args.suite)
    modifications = {**source_changes(args.source), **builder_changes(args.builder)}
    # Both modes intentionally only check: this script must be explicitly
    # invoked with --apply before a future Android candidate build.
    if getattr(args, "apply", False):
        for path, content in modifications.items():
            path.write_text(content, encoding="utf-8")
        target = args.builder / "templates/android"
        target.mkdir(parents=True, exist_ok=True)
        for filename in ("lightcraft_updates.rs", "lightcraft_updates.java.inc"):
            shutil.copy2(args.suite / "tools/lightcraft" / filename, target / filename)
        print("Applied LightCraft v0.18 source and Android builder patches to local copies only.")
    else:
        print(f"PASS: v0.18 patch anchors and Lc SAF protections validated ({len(modifications)} files, read-only).")
    print("NO APK, signing or publication.")


if __name__ == "__main__":
    # --apply is opt-in; all other invocations are validation-only.
    import sys
    apply = "--apply" in sys.argv
    if apply:
        sys.argv.remove("--apply")
    # Local explicit marker for the normal argparse handler.
    old_parse = argparse.ArgumentParser.parse_args
    if apply:
        def parse_with_apply(self, *args, **kwargs):
            result = old_parse(self, *args, **kwargs)
            result.apply = True
            return result
        argparse.ArgumentParser.parse_args = parse_with_apply
    main()
