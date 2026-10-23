"""Scoped LightCraft-only Android integration over the immutable reviewed builder.

Run AFTER source provenance audit and BEFORE bash builder/build.sh -lightcraft.
Never modifies the committed user-approved icon, upstream engine or another app.
"""
from pathlib import Path
import argparse
import ast


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError(f"STOP: reviewed builder drift in {label}: {text.count(old)} anchors")
    return text.replace(old, new, 1)


def apply(builder: Path, source: Path, suite: Path):
    assert (suite / "assets/lightcraft/lc-user-approved.png").is_file()
    # The committed icon is byte-identical to the user's uploaded PNG.
    # Do not crop, repaint, neutralize its highlights or recolor the LC glass.
    # The original icon is a complete blue rounded-square tile, NOT a
    # foreground glyph to background-strip and shrink to 66dp.
    # Render the original pixel artwork as a comfortably inset full icon on
    # Android's 108dp adaptive canvas. Its background uses the actual blue
    # from an interior sample so MagicOS never shows the wrong teal surround.
    icons = builder / "lib/app_icons.py"
    original = icons.read_text()
    anchor = (
        "    stripped, _changed = _strip_background(work, pristine=pristine)\\n"
        "    foreground = _foreground(Image, stripped)"
    )
    replacement = (
        "    if app == 'lightcraft' and explicit is not None:\\n"
        "        sample = pristine.getpixel((WORK_PX // 2, WORK_PX // 4))\\n"
        "        color = '#%02X%02X%02X' % sample[:3]\\n"
        "        # Preserve every original pixel; only scale and center the full tile.\\n"
        "        side = round(CANVAS_PX * 0.85)\\n"
        "        icon = pristine.resize((side, side), Image.Resampling.LANCZOS)\\n"
        "        foreground = Image.new('RGBA', (CANVAS_PX, CANVAS_PX), (0, 0, 0, 0))\\n"
        "        foreground.alpha_composite(icon, ((CANVAS_PX-side)//2, (CANVAS_PX-side)//2))\\n"
        "    else:\\n"
        "        stripped, _changed = _strip_background(work, pristine=pristine)\\n"
        "        foreground = _foreground(Image, stripped)"
    )
    original = replace_once(original, anchor, replacement, "exact approved adaptive icon")
    ast.parse(original)
    icons.write_text(original)

    generator = builder / "lib/build-common.sh"
    script = generator.read_text()
    java_anchor = '        (java_dir / f"{saf[\'activity\']}.java").write_text(java_src)'
    java_new = (
        '        if app == "lightcraft":\n'
        '            inc = (root / "templates/android/lightcraft_updates.java.inc").read_text()\n'
        '            if not java_src.rstrip().endswith("}"):\n'
        '                raise SystemExit("STOP: Android Activity template changed")\n'
        '            pos = java_src.rfind("}")\n'
        '            java_src = java_src[:pos] + inc + "\\n" + java_src[pos:]\n'
        + java_anchor
    )
    script = replace_once(script, java_anchor, java_new, "Java Activity injection")
    manifest_anchor = '    (staging_dir / "Cargo.toml").write_text(manifest)'
    manifest_new = (
        '    if app == "lightcraft":\n'
        '        manifest = manifest.replace("[package.metadata.android.application]",\n'
        '            \'[[package.metadata.android.uses_permission]]\\nname = "android.permission.INTERNET"\\n\\n[package.metadata.android.application]\', 1)\n'
        + manifest_anchor
    )
    script = replace_once(script, manifest_anchor, manifest_new, "Internet permission")
    rust_anchor = '    (staging_dir / "src" / "lib.rs").write_text(entry)'
    rust_new = (
        '    if app == "lightcraft":\n'
        '        entry = entry.replace("mod ime_bridge;", "mod ime_bridge;\\nmod lightcraft_updates;", 1)\n'
        '        entry = entry.replace("bars_theme: Option<bool>,", "bars_theme: Option<bool>,\\n    updates: lightcraft_updates::Updater,", 1)\n'
        '        entry = entry.replace("bars_theme: None", "bars_theme: None, updates: lightcraft_updates::Updater::default()", 1)\n'
        '        entry = entry.replace("self.inner.ui(ui);", "self.inner.ui(ui);\\n        self.updates.ui(ui.ctx(), &self.app);", 1)\n'
        '        for must in ("mod lightcraft_updates;", "updates: lightcraft_updates::Updater,", "self.updates.ui(ui.ctx(), &self.app);"):\n'
        '            if must not in entry:\n'
        '                raise SystemExit("STOP: LightCraft updater bridge injection failed")\n'
        '        (staging_dir / "src" / "lightcraft_updates.rs").write_text(\n'
        '            (root / "templates/android/lightcraft_updates.rs").read_text())\n'
        + rust_anchor
    )
    script = replace_once(script, rust_anchor, rust_new, "Rust updater host")
    # Reviewed inputs were already checked by the immutable source preflight.
    generator.write_text(script)

    menus = source / "crates/ui-egui/src/menus.rs"
    txt = menus.read_text()
    # The Help menu remains LightCraft's native menu; these commands are
    # Android-only and use an egui flag consumed by the Android host.
    txt = replace_once(txt,
        '    ("app.about", "About LightCraft", None, "Help"),',
        '    ("app.about", "About LightCraft", None, "Help"),\n'
        '    ("app.artcraftCheckUpdates", "Check for Updates", None, "Help"),\n'
        '    ("app.artcraftStartupUpdateSettings", "Startup Update Settings", None, "Help"),',
        "LightCraft Android Help command registry")
    txt = replace_once(txt,
        '        "app.export" => crate::control::export_active(app, p),',
        ''
        '        "app.artcraftCheckUpdates" => {\n'
        '            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.lightcraft.check_updates_requested"), true));\n'
        '            ctx.request_repaint();\n'
        '            Ok(Value::Null)\n'
        '        },\n'
        '        "app.artcraftStartupUpdateSettings" => {\n'
        '            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.lightcraft.startup_updates_requested"), true));\n'
        '            ctx.request_repaint();\n'
        '            Ok(Value::Null)\n'
        '        },\n'
        '        "app.export" => crate::control::export_active(app, p),',
        "LightCraft Android Help command handler")
    # Replace the Android updater's separate floating windows with a tab of
    # LightCraft's native Help > About dialog. Do not modify any upstream
    # desktop build; this is applied only to the Android checkout in CI.
    dialogs = source / "crates/ui-egui/src/panels/dialogs.rs"
    dlg = dialogs.read_text()
    dlg = replace_once(dlg,
        'pub const ABOUT_TABS: &[(&str, &str)] = &[("about", "About"), ("contributors", "Contributors"), ("models", "Models")];',
        'pub const ABOUT_TABS: &[(&str, &str)] = &[("about", "About"), ("contributors", "Contributors"), ("models", "Models"), ("updates", "Updates")];',
        "About LightCraft Updates tab")
    dlg = replace_once(dlg,
        '                        2 => crate::credits::models_ui(ui),\n                        _ => {',
        '''
                        2 => crate::credits::models_ui(ui),
                        3 => {
                            ui.heading("LightCraft Updates");
                            let ctx = ui.ctx().clone();
                            let installed = format!("Installed: {}", env!("CARGO_PKG_VERSION"));
                            ui.label(installed);
                            let state_id = egui::Id::new("artcraft.lightcraft.update_status");
                            let state = ctx.data(|d| d.get_temp::<String>(state_id))
                                .unwrap_or_else(|| "Select Check for Updates to query GitHub Releases.".into());
                            ui.label(state);
                            if ui.button("Check for Updates").clicked() {
                                ctx.data_mut(|d| d.insert_temp(
                                    egui::Id::new("artcraft.lightcraft.check_updates_requested"), true));
                                ctx.request_repaint();
                            }
                            ui.separator();
                            let startup_id = egui::Id::new("artcraft.lightcraft.startup_enabled");
                            let mut startup = ctx.data(|d| d.get_temp::<bool>(startup_id)).unwrap_or(false);
                            if ui.checkbox(&mut startup, "Check for updates at startup").changed() {
                                ctx.data_mut(|d| {
                                    d.insert_temp(egui::Id::new("artcraft.lightcraft.startup_desired"), startup);
                                    d.insert_temp(egui::Id::new("artcraft.lightcraft.startup_changed"), true);
                                });
                                ctx.request_repaint();
                            }
                            ui.small("Off by default. Update checks never block photo editing.");
                            let page = ctx.data(|d| d.get_temp::<String>(
                                egui::Id::new("artcraft.lightcraft.release_page")));
                            if page.is_some() && ui.button("Open GitHub Release").clicked() {
                                ctx.data_mut(|d| d.insert_temp(
                                    egui::Id::new("artcraft.lightcraft.open_release_requested"), true));
                                ctx.request_repaint();
                            }
                            ui.small("LightCraft-only GitHub Releases; updates must use the original app signature.");
                        }
                        _ => {''',
        "native About dialog update controls")
    dialogs.write_text(dlg)

    menus.write_text(txt)
    layout = source / "crates/ui-egui/src/menubar.rs"
    lt = layout.read_text()
    lt = replace_once(lt,
        '            "app.about",\n        ],',
        '            "app.about",\n'
        '            "app.artcraftCheckUpdates",\n'
        '            "app.artcraftStartupUpdateSettings",\n'
        '        ],',
        "Help menu layout directly under About LightCraft")
    layout.write_text(lt)
    import shutil
    templates = builder / "templates/android"
    shutil.copy2(suite / "tools/lightcraft/lightcraft_updates.rs", templates / "lightcraft_updates.rs")
    shutil.copy2(suite / "tools/lightcraft/lightcraft_updates.java.inc", templates / "lightcraft_updates.java.inc")
    # The Python builder's source-provenance check MUST run before this patch.
    print("LightCraft-only adaptive icon + Help/Android updater patch staged; no other app changed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--builder", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--suite", type=Path, required=True)
    args = p.parse_args()
    apply(args.builder, args.source, args.suite)
