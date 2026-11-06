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
    # GridCraft v0.15.0 upgraded its whole egui family to the pinned
    # storytold/egui 0.37 fork. The older Android wrapper generator hardcodes
    # egui-winit = 0.36, which can create a second incompatible egui/winit tree.
    # Only switch the disposable v0.15.0 candidate; do not touch tested 0.11.
    workspace = staging_dir.parent.parent / "Cargo.toml"
    if workspace.is_file():
        import tomllib
        upstream_version = tomllib.loads(workspace.read_text())["workspace"]["package"]["version"]
        if upstream_version in ("0.15.0", "0.16.1"):
            cargo = replace_exact(cargo, 'egui-winit = "0.36"',
                                  'egui-winit = "0.37"')
            # GridCraft v0.15's official egui-winit 0.37 fork removed the
            # builder's old android_activity::set_activity helper (E0433).
            # The Android activity is already owned by AndroidApp and passed
            # through eframe NativeOptions; JNI clipboard is handled by our
            # AndroidShell, so this stale registration is not required.
            rust = replace_exact(
                rust,
                '    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());',
                '    // GridCraft v0.15 (egui 0.37): NativeOptions.android_app already owns the activity.',
            )
            # GridCraft v0.15 added ctx to SheetApp::raw_input_hook
            # (E0061). Restrict the change to the new upstream version.
            rust = replace_exact(
                rust,
                '        self.inner.raw_input_hook(raw);',
                '        self.inner.raw_input_hook(ctx, raw);',
            )
        elif upstream_version != "0.11.1":
            raise RuntimeError(f"GridCraft Android overlay rejects unknown upstream version {upstream_version}")
    if MODULE in rust or JAVA_MARKER in java:
        raise RuntimeError("GridCraft enhancements are already installed; refusing duplicate overlay")

    rust = replace_exact(rust, "mod ime_bridge;", "mod ime_bridge;\nmod gridcraft_tools;")
    rust = replace_exact(rust, "probe: InputProbe,", "probe: InputProbe,\n    tools: gridcraft_tools::GridCraftTools,")
    rust = replace_exact(rust, "let ime = ime_bridge::ime::ImeBridge::new(&app);",
                         "let tools = gridcraft_tools::GridCraftTools::new(&app);" + chr(10) + "        let ime = ime_bridge::ime::ImeBridge::new(&app);")
    rust = replace_exact(rust, "probe: InputProbe::default(),",
                         "probe: InputProbe::default(), tools,")
    rust = replace_exact(rust, "self.poll_file_picker();", "self.poll_file_picker();\n        self.tools.poll();")
    rust = replace_exact(rust, "system_fonts::install_system_fonts(ui.ctx());",
                         "system_fonts::install_system_fonts(ui.ctx());\n        self.tools.ui(ui, &mut self.inner);")

    rust = replace_exact(rust, "self.inner.logic(ctx);", "self.tools.close_shortcut(&mut self.inner,ctx);\n        self.tools.editor_escape(&mut self.inner,ctx);\n        self.inner.android_capture_unsaved_dcs(ctx);\n        self.tools.unsaved_dialog(self.inner.android_unsaved_dcs_active(),ctx);\n        self.inner.logic(ctx);")
    rust = replace_exact(rust, "self.inner.ui(ui);", "self.inner.ui(ui);\n        self.tools.editor_escape(&mut self.inner,ui.ctx());\n        self.tools.unsaved_dialog(self.inner.android_unsaved_dcs_active(),ui.ctx());")

    java = replace_exact(java, "super.onActivityResult(requestCode, resultCode, data);",
                         "super.onActivityResult(requestCode, resultCode, data);\n        if (gcHandleActivityResult(requestCode, resultCode, data)) return;")
    java = replace_exact(java, "super.onCreate(savedInstanceState);",
                         "super.onCreate(savedInstanceState);\n        gcStartIfEnabled();")
    if not java.rstrip().endswith("}"):
        raise RuntimeError("Unexpected GridCraft Java Activity ending")
    # User-controlled, one-shot APK downloader is GridCraft v0.15-only.
    # Keep the production signature/package verification in the Java Activity;
    # test builds have .candidate package and cannot self-update to production.
    updater_java = addon_dir / "GridCraftSafeUpdater.java.inc"
    if not updater_java.is_file():
        raise RuntimeError("GridCraft safe Android updater source absent")
    android_updater = updater_java.read_text()
    java = java.rstrip()[:-1] + "\n" + addon_java.read_text() + "\n" + android_updater + "\n}\n"
    if "android.permission.INTERNET" not in cargo:
        cargo += '\n[[package.metadata.android.uses_permission]]\nname = "android.permission.INTERNET"\n'
    if android_updater and "android.permission.REQUEST_INSTALL_PACKAGES" not in cargo:
        # Needed to show Android's user-confirmed package installer, never to
        # silently grant install permission.
        cargo += '\n[[package.metadata.android.uses_permission]]\nname = "android.permission.REQUEST_INSTALL_PACKAGES"\n'

    # Validate every source transformation before writing any files.
    if workspace.is_file() and upstream_version in ("0.15.0", "0.16.1"):
        assert 'egui_winit::android_activity::set_activity(' not in rust
        assert rust.count("self.inner.raw_input_hook(ctx, raw);") == 1
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
