"""Install GridCraft-only Android enhancements into an *ephemeral generated* launcher.

Run by the isolated builder generator, after it has populated staging_dir but
before moving that directory into place. Never modifies upstream workbook crates.
"""
from pathlib import Path
import shutil

MODULE = "GRIDCRAFT_ANDROID_TOOLS_V1"
JAVA_MARKER = "GRIDCRAFT_ANDROID_ADDONS_V1"

def replace_exact(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"GridCraft source API changed; expected one marker {old!r}, found {source.count(old)}")
    return source.replace(old, new, 1)

def apply_overlay(staging_dir: Path, package_name: str, addon_dir: Path) -> None:
    staging_dir = Path(staging_dir)
    addon_dir = Path(addon_dir)
    if staging_dir.name != "gridcraft-android.artcraft-staging":
        raise RuntimeError("Refusing to patch any Android app other than GridCraft")
    if not package_name.startswith("com.artcraft.gridcraft"):
        raise RuntimeError("Unexpected GridCraft package; do not change package identity without review")
    rust_source = staging_dir / "src/lib.rs"
    cargo_manifest = staging_dir / "Cargo.toml"
    java_source = staging_dir / "java" / Path(*package_name.split(".")) / "GridCraftActivity.java"
    addon_rust = addon_dir / "gridcraft_tools.rs"
    addon_java = addon_dir / "GridCraftJavaMethods.java.inc"
    for path in (rust_source, cargo_manifest, java_source, addon_rust, addon_java):
        if not path.is_file():
            raise RuntimeError(f"GridCraft overlay input missing: {path}")

    rust = rust_source.read_text()
    java = java_source.read_text()
    cargo = cargo_manifest.read_text()
    if MODULE in rust or JAVA_MARKER in java:
        raise RuntimeError("GridCraft enhancements are already installed; refusing duplicate overlay")

    rust = replace_exact(rust, "mod ime_bridge;", "mod ime_bridge;\nmod gridcraft_tools;")
    rust = replace_exact(rust, "probe: InputProbe,", "probe: InputProbe,\n    tools: gridcraft_tools::GridCraftTools,")
    rust = replace_exact(rust, "let ime = ime_bridge::ime::ImeBridge::new(&app);",
                         "let tools = gridcraft_tools::GridCraftTools::new(&app);\\n        let ime = ime_bridge::ime::ImeBridge::new(&app);".replace("\\\\n", "\\n"))
    rust = replace_exact(rust, "probe: InputProbe::default(),",
                         "probe: InputProbe::default(), tools,")
    rust = replace_exact(rust, "self.poll_file_picker();", "self.poll_file_picker();\n        self.tools.poll();")
    rust = replace_exact(rust, "system_fonts::install_system_fonts(ui.ctx());",
                         "system_fonts::install_system_fonts(ui.ctx());\n        self.tools.ui(ui, &mut self.inner);")

    java = replace_exact(java, "super.onActivityResult(requestCode, resultCode, data);",
                         "super.onActivityResult(requestCode, resultCode, data);\n        if (gcHandleActivityResult(requestCode, resultCode, data)) return;")
    java = replace_exact(java, "super.onCreate(savedInstanceState);",
                         "super.onCreate(savedInstanceState);\n        gcStartIfEnabled();")
    if not java.rstrip().endswith("}"):
        raise RuntimeError("Unexpected GridCraft Java Activity ending")
    java = java.rstrip()[:-1] + "\n" + addon_java.read_text() + "\n}\n"
    if "android.permission.INTERNET" not in cargo:
        cargo += '\n[[package.metadata.android.uses_permission]]\nname = "android.permission.INTERNET"\n'

    # Validate every source transformation before writing any files.
    assert rust.count("mod gridcraft_tools;") == 1
    assert rust.count("self.tools.ui(ui, &mut self.inner);") == 1
    assert java.count(JAVA_MARKER) == 1
    assert java.count("gcHandleActivityResult(requestCode, resultCode, data)") == 1
    assert "android.permission.INTERNET" in cargo
    rust_source.write_text(rust)
    java_source.write_text(java)
    cargo_manifest.write_text(cargo)
    shutil.copyfile(addon_rust, staging_dir / "src/gridcraft_tools.rs")
    print("GridCraft-only Android overlay staged: fonts, shared SAF folder, updater, shortcut pad")

# runpy.run_path passes precisely these values from the forked builder generator.
if "staging_dir" in globals():
    apply_overlay(staging_dir, package_name, root / "tools/gridcraft_android")
