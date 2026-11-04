#!/usr/bin/env python3
"""Restore Android-specific DesignCraft controls when building pinned v0.17.0.

Run after the generic launcher is staged, before compiling/signing.
Only operates in the isolated, debug-only -designcraft-v016 build path.
All anchors fail closed on upstream API drift; no production changes.
"""
from pathlib import Path
import shutil
import sys

def once(source: str, before: str, after: str, label: str) -> str:
    count = source.count(before)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one {before[:70]!r}, found {count}")
    return source.replace(before, after, 1)

def modify(path: Path, before: str, after: str):
    path.write_text(once(path.read_text(), before, after, str(path)))

def patch_source(src: Path):
    ui = src / "crates/ui-egui/src"
    commands = ui / "menus/ui_commands.rs"
    modify(commands, 'pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[',
        '''pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[
    #[cfg(target_os = "android")]
    ("app.artcraftImportFont", "Import Fonts (TTF/OTF/TTC)…", None, "{}"),''')
    menus = ui / "menus.rs"
    modify(menus, "pub use run::run_ui;",
        '''pub use run::run_ui;
#[cfg(target_os = "android")]
pub use run::take_android_font_import;''')
    run = ui / "menus/run.rs"
    source = run.read_text()
    source = once(source, "use super::export::{",
        '''#[cfg(target_os = "android")]
static ANDROID_IMPORT_FONT: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

#[cfg(target_os = "android")]
pub fn take_android_font_import() -> bool {
    ANDROID_IMPORT_FONT.swap(false, std::sync::atomic::Ordering::Relaxed)
}

use super::export::{''', str(run))
    source = once(source,
        'fn run_ui_inner(app: &mut DesignApp, id: &str, p: &Value) -> Option<Result<Value, String>> {\n',
        '''fn run_ui_inner(app: &mut DesignApp, id: &str, p: &Value) -> Option<Result<Value, String>> {
    #[cfg(target_os = "android")]
    if id == "app.artcraftImportFont" {
        ANDROID_IMPORT_FONT.store(true, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
''', str(run))
    run.write_text(source)
    table = ui / "menus/tables.rs"
    source = table.read_text()
    source = once(source, '            "cmd:file.close",',
        '            "cmd:file.close",\n            "ui:app.artcraftImportFont",', str(table))
    source = once(source, '        "Type",\n        &[\n',
        '        "Type",\n        &[\n            "ui:app.artcraftImportFont",\n            "-",\n', str(table))
    table.write_text(source)

    dialogs = ui / "dialogs.rs"
    source = dialogs.read_text()
    source = once(source,
        '"closeDocument" => crate::i18n::tr(&app.ui.language, "  Save  ").to_string(),',
        '"closeDocument" => format!("{} (S)", crate::i18n::tr(&app.ui.language, "  Save  ").trim()),',
        str(dialogs))
    source = once(source,
        'let cancel = d.id != "alert" && ui.button(crate::rtl::widget(ui, crate::i18n::tr(&app.ui.language, cancel_label))).clicked();',
        '''let cancel_text = if d.id == "closeDocument" {
                    format!("{} (C)", crate::i18n::tr(&app.ui.language, cancel_label))
                } else {
                    crate::i18n::tr(&app.ui.language, cancel_label).to_string()
                };
                let cancel = d.id != "alert" && ui.button(crate::rtl::widget(ui, cancel_text)).clicked();''',
        str(dialogs))
    source = once(source,
        'ui.button(crate::rtl::widget(ui, crate::i18n::tr(&app.ui.language, "Don\'t Save"))).clicked()',
        'ui.button(crate::rtl::widget(ui, format!("{} (D)", crate::i18n::tr(&app.ui.language, "Don\'t Save")))).clicked()',
        str(dialogs))
    source = once(source,
        '    app.ui.dialog = Some(d);\n    match result {',
        '''    #[cfg(target_os = "android")]
    if d.id == "closeDocument" && result.is_none() {
        // Handle each fresh non-repeating physical D/C/S press while the
        // unsaved-document modal is open; subsequent dialogs keep working.
        let action = ctx.input(|i| i.events.iter().find_map(|event| match event {
            egui::Event::Key { key, pressed: true, repeat: false, modifiers, .. }
                if !modifiers.any() => match key {
                    egui::Key::D => Some(1_u8),
                    egui::Key::C => Some(2_u8),
                    egui::Key::S => Some(3_u8),
                    _ => None,
                },
            _ => None,
        }));
        match action {
            Some(1) => { d.fields.insert("discard".into(), json!(true)); result = Some(true); }
            Some(2) => result = Some(false),
            Some(3) => result = Some(true),
            _ => {}
        }
    }
    app.ui.dialog = Some(d);
    match result {''', str(dialogs))
    dialogs.write_text(source)

    fontdb = src / "crates/fonts/src/fontdb/system.rs"
    source = fontdb.read_text()
    anchor = '        dirs.extend(unix_font_dirs(home.as_deref(), xdg_data_home.as_deref()));'
    source = once(source, anchor, anchor + '''
        if cfg!(target_os = "android") {
            // Scan Android system partitions directly, even if symlinks
            // under HOME are not followed by the upstream font enumerator.
            dirs.extend(["/system/fonts", "/product/fonts"].map(Into::into));
        }''', str(fontdb))
    fontdb.write_text(source)

def patch_launcher(root: Path, android: Path):
    launcher = android / "src/lib.rs"
    source = launcher.read_text()
    source = once(source, "mod system_fonts;", "mod v016_android;\nmod system_fonts;", str(launcher))
    source = once(source,
        'inbox.lock().unwrap_or_else(|error| error.into_inner()).push(ImportedFile { request: request.clone(), name, bytes });',
        '''if request.purpose == "android-font" {
                                v016_android::accept_font(&name, &bytes);
                            } else {
                                inbox.lock().unwrap_or_else(|error| error.into_inner())
                                    .push(ImportedFile { request: request.clone(), name, bytes });
                            }''', str(launcher))
    source = once(source, "        self.inner.ui(ui);",
        '''        v016_android::ui(ui, &mut self.inner, &self.saf_bridge, &self.saf_state);
        self.inner.ui(ui);''', str(launcher))
    source = once(
        source,
        "    apply_immersive_fullscreen(&android_app);",
        """    // DesignCraft-only adaptive cursor: publish the Activity before first frame.
    egui_winit::android_activity::set_activity(
        android_app.activity_as_ptr() as *mut std::ffi::c_void
    );
    apply_immersive_fullscreen(&android_app);""",
        "publish Android activity for adaptive cursor",
    )
    launcher.write_text(source)
    manifest = android / "Cargo.toml"
    m = manifest.read_text()
    m = once(m, "[dependencies]\\n", """[dependencies]
egui-winit = { path = "../../vendor/egui-winit" }
""", "DesignCraft's egui-winit adapter dependency")
    manifest.write_text(m)
    shutil.copyfile(root / "tools/designcraft/v016_android.rs", android / "src/v016_android.rs")

    # Preserve the old release's writable font import layout.
    sys.path.insert(0, str(root / "tools/designcraft"))
    from prepare_builder import patch_android_font_paths
    fonts = android / "src/system_fonts.rs"
    fonts.write_text(patch_android_font_paths(fonts.read_text()))

def install_icons(root: Path, src: Path, android: Path):
    # Exact user-approved glass "Dc" resources, checked by the suite manifest.
    sys.path.insert(0, str(root / "tools/approved-branding"))
    import approved_branding
    cfg = approved_branding.check_assets()
    if cfg["app"] != "designcraft":
        raise ValueError("Wrong app in approved icon manifest")
    res_dir = root / "tools/approved-branding/assets/res"
    dest_dir = android / "res"
    for old in dest_dir.rglob("*"):
        if old.is_file() and old.stem in {"ic_launcher", "ic_launcher_round", "ic_launcher_foreground"}:
            old.unlink()
    for file in res_dir.rglob("*"):
        if file.is_file():
            rel = file.relative_to(res_dir)
            if str(rel) == "values/colors.xml":
                rel = Path("values/approved_brand_colors.xml")
            dest = dest_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, dest)
    (dest_dir / "values/approved_brand_colors.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<resources><color name="approved_launcher_background">{cfg["bg_color"]}</color></resources>\n'
    )
    for xml in (dest_dir / "mipmap-anydpi-v26").glob("*.xml"):
        xml.write_text(xml.read_text()
            .replace("artcraft_icon_background", "approved_launcher_background")
            .replace("ic_launcher_background", "approved_launcher_background"))
    manifest = android / "Cargo.toml"
    original = manifest.read_text()
    import re
    updated, matches = re.subn(r'^icon\s*=\s*"[^"]+"', 'icon = "@mipmap/ic_launcher"', original, count=1, flags=re.M)
    if matches != 1:
        raise ValueError("Missing generated launcher icon field")
    # Keep the upstream v0.17 core pinned while identifying the Android build
    # separately. Do not change the signing identity or published release.
    candidate_version = "0.17.0-android.1"
    if updated.count("version.workspace = true") != 1:
        raise ValueError("Generated Android manifest version changed")
    updated = updated.replace("version.workspace = true",
                              f'version = "{candidate_version}"', 1)
    updated, named = re.subn(r'^apk_name\s*=\s*"[^"]+"',
                             f'apk_name = "designcraft-{candidate_version}"',
                             updated, count=1, flags=re.M)
    if named != 1:
        raise ValueError("Generated APK name changed")
    # cargo-apk2 v1.5 derives versionCode from the package version.
    # Setting package.metadata.android.version_code panics before compilation.
    # Keep android.N in versionName; let cargo-apk2 calculate the integer code.
    if updated.count("[package.metadata.android]") != 1:
        raise ValueError("Missing Android package metadata")
    # The upstream v0.17 update UI needs Android Internet permission to
    # resolve GitHub hosts; the generic launcher did not request it.
    if 'android.permission.INTERNET' not in updated:
        updated += ('\n[[package.metadata.android.uses_permission]]\n'
                    'name = "android.permission.INTERNET"\n')
    manifest.write_text(updated)

    # About dialog and app header should show the same design instead of cat.
    # This copies the approved texture while leaving upstream generic icons.
    approved_branding.ui_brand(src, "designcraft")
    print("DesignCraft v0.17: installed approved glossy Dc launcher and in-app brand")

def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: patch_v016_android.py REPO_ROOT SOURCE_DIR ANDROID_DIR")
    root, src, android = map(lambda p: Path(p).resolve(), sys.argv[1:])
    if src.name != "designcraft" or android.name != "designcraft-android":
        raise SystemExit("Refusing to patch any non-DesignCraft Android source")
    if not (root / "configs/upstream/designcraft-v017.json").is_file():
        raise SystemExit("Missing DesignCraft pinned upstream v0.17 manifest")
    patch_source(src)
    patch_launcher(root, android)
    # Integrate existing Android SAF folder scanner and physical keys only
    # for the isolated v0.17 review; other applications remain unchanged.
    from patch_v017_interactions import ui_source, launcher, java_source
    ui_source(src)
    launcher(android)
    java_source(root, android)
    install_icons(root, src, android)
    from install_v017_updater import apply as install_updater
    install_updater(root, src, android)
    print("DesignCraft v0.17: Android font import, modal D/C/S, updater and branding staged")

if __name__ == "__main__":
    main()
