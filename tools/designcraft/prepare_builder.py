"""Apply version metadata to the pinned Android builder without editing official app source."""
import argparse
from pathlib import Path
import re
import shutil
from menu_overlay import apply as install_android_menus


def patch_android_font_paths(text: str) -> str:
    """Align the pinned DesignCraft Android font scanner with writable font imports."""
    legacy_link = '''        if !link.exists() {
            let _ = std::os::unix::fs::symlink("/system/fonts", &link);
        }
'''
    writable_link = '''        // Only replace legacy links to Android's read-only system directory;
        // leave real user directories and already-imported fonts untouched.
        if std::fs::read_link(&link).ok().as_deref()
            == Some(std::path::Path::new("/system/fonts"))
        {
            let _ = std::fs::remove_file(&link);
        }
        if std::fs::create_dir_all(&link).is_ok() {
            let system_link = link.join("android-system");
            if std::fs::symlink_metadata(&system_link).is_err() {
                let _ = std::os::unix::fs::symlink("/system/fonts", &system_link);
            }
        }
'''
    if text.count(legacy_link) != 1:
        raise ValueError("Pinned Android font directory bootstrap changed; review required")
    text = text.replace(legacy_link, writable_link)
    xdg = 'std::env::set_var("XDG_DATA_HOME", &base);'
    if text.count(xdg) != 1:
        raise ValueError("Pinned Android XDG font search path changed; review required")
    return text.replace(xdg,
        'std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));')


def prepare(root: Path, version: str, code: int):
    if not re.fullmatch(r"\d+\.\d+\.\d+-android\.[1-9]\d*", version):
        raise ValueError("Expected MAJOR.MINOR.PATCH-android.REVISION")
    if not 1 <= code <= 2100000000:
        raise ValueError("versionCode must be between 1 and 2100000000")
    script = root / "lib/build-common.sh"
    project = root / "lib/android_project.py"
    source = script.read_text()
    needle = 'python3 "$ROOT/lib/android_project.py" "$ROOT" "$ANDROID_DIR" "$APP" "$APP_VERSION"'
    if source.count(needle) != 1:
        raise ValueError("Pinned builder generation command changed; review required")
    generated = project.read_text()
    code_needle = '    code = version_code(version)'
    if generated.count(code_needle) != 1:
        raise ValueError("Pinned builder versionCode generation changed; review required")
    # Literal values have already been constrained to numbers, dots and hyphens.
    source = source.replace(needle, needle.rsplit('"$APP_VERSION"', 1)[0] + f'"{version}"')
    generated = generated.replace(code_needle, f'    code = {code}')
    hook = '[[ -f "$ANDROID_DIR/Cargo.toml" && -f "$ANDROID_DIR/src/lib.rs" ]]'
    if source.count(hook) != 1:
        raise ValueError("Launcher completion hook changed")
    source = source.replace(hook, 'python3 "$ROOT/designcraft-support/patch_launcher.py" "$ANDROID_DIR"\n\n' + hook)
    branding_hook = 'say 5 "Preparing a builder-owned signing key..."'
    if source.count(branding_hook) != 1:
        raise ValueError("Pinned Android branding insertion point changed")
    source = source.replace(branding_hook,
        'python3 "$ROOT/designcraft-support/apply_approved_branding.py" "$ROOT" "$ANDROID_DIR" "$VERSION_NAME"\\n\\n' + branding_hook)
    shutil.copytree(Path(__file__).parent / "support", root / "designcraft-support", dirs_exist_ok=True)
    shutil.copytree(Path(__file__).parents[1] / "approved-branding", root / "designcraft-approved", dirs_exist_ok=True)
    install_android_menus(root / "source/designcraft/crates/ui-egui/src/menus.rs")
    # DesignCraft's TTF/OTF importer writes under $HOME/.local/share/fonts/imported,
    # and its SAF shared-folder cache uses the same internal app-data root.
    # The pinned builder otherwise points XDG_DATA_HOME to `base`, so DesignCraft's
    # font database scans `base/fonts` instead of the imported fonts. Keep the
    # override DesignCraft-only; no other Craft apps' font paths are changed.
    fonts = root / "templates/android/system_fonts.rs"
    fonts.write_text(patch_android_font_paths(fonts.read_text()))
    # Generate both legacy and adaptive layers from the approved glossy source.
    icon_module = root / "lib/app_icons.py"
    icon_source = icon_module.read_text()
    icon_anchor = "    Image, _ = _pillow()\n    source = pick_source(src, app, explicit)"
    if icon_source.count(icon_anchor) != 1:
        raise ValueError("Pinned icon generator changed")
    icon_module.write_text(icon_source.replace(icon_anchor,
        "    if app == 'designcraft' and explicit is not None:\n"
        "        import designcraft_launcher\n"
        "        return designcraft_launcher.generate(explicit, res_dir)\n" + icon_anchor, 1))
    shutil.copyfile(Path(__file__).with_name("launcher_icon.py"), root / "lib/designcraft_launcher.py")
    script.write_text(source)
    project.write_text(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("version")
    parser.add_argument("version_code", type=int)
    args = parser.parse_args()
    prepare(args.builder, args.version, args.version_code)

