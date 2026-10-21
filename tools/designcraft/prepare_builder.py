"""Apply version metadata to the pinned Android builder without editing official app source."""
import argparse
from pathlib import Path
import re
import shutil
from menu_overlay import apply as install_android_menus


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
    shutil.copytree(Path(__file__).parent / "support", root / "designcraft-support", dirs_exist_ok=True)
    install_android_menus(root / "source/designcraft/crates/ui-egui/src/menus.rs")
    fonts = root / "templates/android/system_fonts.rs"
    text = fonts.read_text().replace('std::os::unix::fs::symlink("/system/fonts", &link)', 'std::fs::create_dir_all(&link).and_then(|_| std::os::unix::fs::symlink("/system/fonts", link.join("android-system")))')
    fonts.write_text(text)
    script.write_text(source)
    project.write_text(generated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("version")
    parser.add_argument("version_code", type=int)
    args = parser.parse_args()
    prepare(args.builder, args.version, args.version_code)
