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
    icons = builder / "lib/app_icons.py"
    original = icons.read_text()
    old = "    work = _raster(source)\n    color = _background_color(Image, work)"
    # Scope the derived borderless artwork to LightCraft. Both legacy and adaptive
    # resource generators get the derived pixels; the approved original is unchanged.
    new = (
        "    work = _raster(source)\n"
        "    if app == 'lightcraft' and explicit is not None:\n"
        "        work = _lightcraft_borderless(Image, work)\n"
        "    color = _background_color(Image, work)"
    )
    original = replace_once(original, old, new, "icon render")
    original = replace_once(original,
        "    _write_legacy(source, pristine, res_dir)",
        "    _write_legacy(None if app == 'lightcraft' and explicit is not None else source, pristine, res_dir)",
        "legacy icon")
    original = replace_once(original,
        "        if magick:\n            subprocess.run(",
        "        if magick and source is not None:\n            subprocess.run(",
        "legacy renderer")
    anchor = "\ndef generate(src: Path, app: str, res_dir: Path, explicit: Path = None) -> Path:\n"
    algorithm = '''
def _lightcraft_borderless(Image, img):
    """Derive launcher-only deep-blue tile from the approved image, excluding white frame.

    Find dark blue interior at central horizontal/vertical cross-sections rather
    than bleaching near-white letters (their specular highlights must survive).
    This changes the *Android derived launcher resources*, NOT the approved PNG.
    """
    w, h = img.size
    px = img.load()
    def blue(x, y):
        r, g, b, a = px[x, y]
        return a >= 190 and b >= 75 and b > r * 1.3 and r < 145 and (b - r) > 25
    def run_at_horizontal(y):
        xs = [x for x in range(w // 7, w * 6 // 7) if blue(x, y)]
        return (min(xs), max(xs)) if len(xs) > w // 3 else None
    def run_at_vertical(x):
        ys = [y for y in range(h // 7, h * 6 // 7) if blue(x, y)]
        return (min(ys), max(ys)) if len(ys) > h // 3 else None
    x_ranges = [v for y in (h // 3, h * 2 // 3) if (v := run_at_horizontal(y))]
    y_ranges = [v for x in (w // 3, w * 2 // 3) if (v := run_at_vertical(x))]
    if len(x_ranges) != 2 or len(y_ranges) != 2:
        raise RuntimeError("STOP: approved Lc tile not recognized; do not alter launcher icon")
    # The border occupies the outer band around the dark blue tile.
    left = max(0, min(v[0] for v in x_ranges) + 2)
    top = max(0, min(v[0] for v in y_ranges) + 2)
    right = min(w, max(v[1] for v in x_ranges) - 1)
    bottom = min(h, max(v[1] for v in y_ranges) - 1)
    if not (0.64*w < right-left < 0.96*w and 0.64*h < bottom-top < 0.96*h):
        raise RuntimeError("STOP: Lc border crop exceeds accepted geometry")
    return img.crop((left, top, right, bottom)).resize((w, h), Image.Resampling.LANCZOS)

'''
    original = replace_once(original, anchor, "\n"+algorithm+anchor, "icon helper")
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
    # Check the embedded Python heredoc, not the outer shell.
    anchor = "python3 - \"$ROOT\" \"$APP\" \"$TITLE\" \"$ANDROID_DIR\" \"$PACKAGENAME\" \"$APPICON\" <<'PY'"
    if anchor not in script:
        raise RuntimeError("STOP: generator Python heredoc changed")
    generator.write_text(script)

    menus = source / "crates/ui-egui/src/menus.rs"
    txt = menus.read_text()
    txt = replace_once(txt,
        '    ("app.whatsNew", "What\'s New", None, "Help"),',
        '    ("app.whatsNew", "What\'s New", None, "Help"),\n    ("app.artcraftCheckUpdates", "Check for Updates", None, "Help"),',
        "LightCraft command registry")
    txt = replace_once(txt,
        '        "app.export" => crate::control::export_active(app, p),',
        ''
        '        "app.artcraftCheckUpdates" => {\n'
        '            ctx.data_mut(|d| d.insert_temp(egui::Id::new("artcraft.lightcraft.check_updates_requested"), true));\n'
        '            ctx.request_repaint();\n'
        '            Ok(Value::Null)\n'
        '        },\n'
        '        "app.export" => crate::control::export_active(app, p),',
        "LightCraft command handler")
    menus.write_text(txt)
    layout = source / "crates/ui-egui/src/menubar.rs"
    lt = layout.read_text()
    lt = replace_once(lt,
        '            "app.whatsNew",\n            "app.shortcuts",',
        '            "app.whatsNew",\n            "app.artcraftCheckUpdates",\n            "app.shortcuts",',
        "Help menu layout")
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
