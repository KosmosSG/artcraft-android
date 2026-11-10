#!/usr/bin/env python3
"""LightCraft v0.20-only Android compatibility patch.

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
UPSTREAM = "192ff72923c39e6623f2c7ff67ab3a119deb8071"
APP = "lightcraft"


def once(text: str, old: str, new: str, label: str) -> str:
    hits = text.count(old)
    if hits != 1:
        raise ValueError(f"STOP: LightCraft v0.20 {label}: expected 1 anchor; got {hits}")
    return text.replace(old, new, 1)


def legacy_payload(label: str) -> tuple[str, str]:
    """Resolve literal string expressions in the protected old script, without executing it."""
    tree = ast.parse((SUITE / "tools/lightcraft/apply_android_fixes.py").read_text())
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "apply")
    env: dict[str, str] = {}

    def literal(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name) and node.id in env:
            return env[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return literal(node.left) + literal(node.right)
        raise ValueError("STOP: published LightCraft replacement is not a static string")

    for statement in fn.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            try:
                env[statement.targets[0].id] = literal(statement.value)
            except ValueError:
                pass
        for call in ast.walk(statement):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "replace_once" and len(call.args) == 4):
                continue
            try:
                found_label = literal(call.args[3])
            except ValueError:
                continue
            if found_label == label:
                return literal(call.args[1]), literal(call.args[2])
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
        "cargo_ui": source / "crates/ui-egui/Cargo.toml",
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
    # The upstream UI crate does not register an image loader. Without this,
    # the embedded LC PNG renders as egui's red warning triangle.
    # Upstream v0.20 already declares egui_extras: add only the image loader feature.
    cargo_ui = once(originals["cargo_ui"],
        'egui_extras = { workspace = true }',
        'egui_extras = { workspace = true, features = ["image"] }\nimage = { workspace = true, features = ["png"] }',
        "LC PNG image loader dependencies")
    # Android-only compact Lc menu: reuse existing appearance/update commands.
    # Keep the desktop menu unchanged and do not add font controls.
    m = once(m,
        'pub fn show_in_window(app: &mut LightcraftApp, ui: &mut egui::Ui, max_width: f32) -> f32 {\n',
        '''pub fn show_in_window(app: &mut LightcraftApp, ui: &mut egui::Ui, max_width: f32) -> f32 {
    #[cfg(target_os = "android")]
    {
        egui_extras::install_image_loaders(ui.ctx());
        let artwork = egui::Image::from_bytes("bytes://lightcraft/lc-menu.png", include_bytes!("lc-menu.png"))
            .fit_to_exact_size(egui::vec2(22.0, 22.0));
        let icon = ui.add(egui::Button::image(artwork).frame(false));
        crate::widgets::register(ui, "menu:Lc", icon.rect);
        let mut choice: Option<(&str, Value)> = None;
        egui::Popup::menu(&icon).show(|ui| {
            ui.set_min_width(180.0);
            ui.menu_button("Appearance", |ui| {
                if ui.button("Light").clicked() {
                    choice = Some(("view.appearance", json!({"mode":"light"})));
                    ui.close();
                }
                if ui.button("Dark").clicked() {
                    choice = Some(("view.appearance", json!({"mode":"dark"})));
                    ui.close();
                }
            });
            ui.separator();
            if ui.button("Check for Updates").clicked() {
                choice = Some(("app.checkForUpdates", Value::Null));
                ui.close();
            }
            if ui.button("Startup Update Settings").clicked() {
                choice = Some(("app.artcraftStartupUpdateSettings", Value::Null));
                ui.close();
            }
            ui.separator();
            if ui.button("About LightCraft").clicked() {
                choice = Some(("app.about", Value::Null));
                ui.close();
            }
        });
        if let Some((id, params)) = choice {
            let _ = run_item(app, id, params);
        }
        ui.add_space(8.0);
    }
''',
        "Android compact Lc top-left menu")
    # Make native Android menu hover selection visible, matching compact GC style.
    # Preserve menu click dispatch, access keys and all non-Android styling.
    m = once(m,
        '                let r = ui.add_enabled(*enabled, b);',
        '''                #[cfg(target_os = "android")]
                let b = {
                    let hover_color = ui.visuals().widgets.hovered.bg_fill;
                    let hover_color = if hover_color == egui::Color32::TRANSPARENT {
                        egui::Color32::from_gray(70)
                    } else {
                        hover_color
                    };
                    b.fill(if ui.ctx().pointer_hover_pos().is_some_and(|p| {
                        let top = ui.next_widget_position().y;
                        p.y >= top && p.y < top + ui.spacing().interact_size.y
                            && p.x >= ui.min_rect().left() && p.x <= ui.max_rect().right()
                    }) { hover_color } else { egui::Color32::TRANSPARENT })
                };
                let r = ui.add_enabled(*enabled, b);''',
        "Android menu row hover highlight")
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
    return {paths["commands"]: c, paths["menubar"]: m, paths["run"]: run, paths["dialogs"]: dlg, paths["cargo_ui"]: cargo_ui}


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
    # Other builder tables also contain a LightCraft entry; inspect only SAF_RECIPES.
    saf_region = script.split("SAF_RECIPES = {", 1)
    if len(saf_region) != 2:
        raise ValueError("STOP: Android SAF recipe table is missing")
    saf_region = saf_region[1].split('    "cadcraft": {', 1)[0]
    if saf_region.count('    "lightcraft": {') != 1:
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
    if hashlib.sha256((suite / "assets/lightcraft/lc-user-20261109.png").read_bytes()).hexdigest() != "22a5a153cac7b620fdc061e80c86d3f4d01fd7992f6b4f2653a086ac560ba456":
        raise ValueError("STOP: replacement owner-provided LC icon hash drift")
    import subprocess
    checked = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True)
    if checked.returncode or checked.stdout.strip() != UPSTREAM:
        raise ValueError("STOP: wrong official upstream LightCraft commit")
    if 'version = "0.20.0"' not in (source / "Cargo.toml").read_text(encoding="utf-8"):
        raise ValueError("STOP: wrong upstream LightCraft version")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--builder", type=Path, required=True)
    p.add_argument("--suite", type=Path, default=SUITE)
    p.add_argument("--apply", action="store_true", help="Modify only local upstream and builder COPIES")
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
        shutil.copy2(args.suite / "assets/lightcraft/lc-user-20261109.png",
                     args.source / "crates/ui-egui/src/menus/lc-menu.png")
        print("Applied LightCraft v0.20 source and Android builder patches to local copies only.")
    else:
        print(f"PASS: v0.20 patch anchors and Lc SAF protections validated ({len(modifications)} files, read-only).")
    print("NO APK, signing or publication.")


if __name__ == "__main__":
    main()
