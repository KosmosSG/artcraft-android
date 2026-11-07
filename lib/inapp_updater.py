#!/usr/bin/env python3
"""Integrate optional updater into freshly generated WordCraft/GridCraft SAF launchers.

This runs AFTER lib/build-common.sh generates the Android launcher, leaving every upstream
engine and existing Android interaction unchanged. It is idempotent on reused checkouts.
For future release branches, update TARGET_TAG for the exact APK version being built.
"""
from pathlib import Path
import re
import shutil
import sys
import tomllib

TARGET_TAG = {
    "wordcraft": "wordcraft-v0.15.2-android.3",
    "gridcraft": "gridcraft-v0.16.1-android.4",
}
ACTIVITY = {
    "wordcraft": "WordCraftActivity",
    "gridcraft": "GridCraftActivity",
}


def replace_once(content: str, old: str, new: str, label: str) -> str:
    if new in content:
        return content
    if content.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {content.count(old)}")
    return content.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: inapp_updater.py APP ANDROID_DIR BUILDER_ROOT")
    app, android_dir, root = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if app not in TARGET_TAG:
        return
    if not android_dir.is_dir():
        raise RuntimeError(f"Android launcher missing: {android_dir}")
    manifest_path = android_dir / "Cargo.toml"
    manifest = manifest_path.read_text()
    metadata = tomllib.loads(manifest)["package"]["metadata"]["android"]
    java_package = metadata["package"]
    if not java_package.startswith("com.artcraft." + app):
        raise RuntimeError(f"Updater refuses unexpected test package: {java_package}")
    java_dir = android_dir / "java" / Path(*java_package.split("."))
    activity_path = java_dir / (ACTIVITY[app] + ".java")
    if not activity_path.is_file():
        raise RuntimeError(f"Expected generated SAF Activity missing: {activity_path}")

    # Android permissions. The OS will still ask before installing an APK.
    for permission in ("android.permission.INTERNET",
                       "android.permission.REQUEST_INSTALL_PACKAGES"):
        if f'name = "{permission}"' not in manifest:
            manifest += (
                "\n[[package.metadata.android.uses_permission]]\n"
                f'name = "{permission}"\n'
            )
    tomllib.loads(manifest)

    updater_java = (root / "templates/android/ArtCraftUpdater.java").read_text()
    updater_java = updater_java.replace("__PACKAGE__", java_package)
    activity_text = activity_path.read_text()
    activity_text = replace_once(
        activity_text,
        "        handleIncomingFiles(getIntent());",
        "        if (!ArtCraftUpdater.handleInstallCallback(this, getIntent()))\n"
        "            handleIncomingFiles(getIntent());",
        "SAF onCreate callback",
    )
    activity_text = replace_once(
        activity_text,
        "        handleIncomingFiles(intent);",
        "        if (!ArtCraftUpdater.handleInstallCallback(this, intent))\n"
        "            handleIncomingFiles(intent);",
        "SAF onNewIntent callback",
    )

    updater_rust = (root / "templates/android/updater.rs").read_text()
    updater_rust = (updater_rust
        .replace("__APP__", app)
        .replace("__INSTALLED_TAG__", TARGET_TAG[app])
        .replace("__TARGET_PACKAGE__", "com.artcraft." + app)
        .replace("__JAVA_CLASS__", java_package.replace(".", "/") + "/ArtCraftUpdater"))
    lib_path = android_dir / "src" / "lib.rs"
    rust = lib_path.read_text()
    rust = replace_once(
        rust,
        "mod ime_bridge;",
        "mod ime_bridge;\nmod updater;",
        "Rust updater import",
    )
    rust = replace_once(
        rust,
        "    probe: InputProbe,",
        "    probe: InputProbe,\n    updater_open: bool,\n    updater_initialized: bool,",
        "Rust shell fields",
    )
    rust = replace_once(
        rust,
        "probe: InputProbe::default()",
        "probe: InputProbe::default(), updater_open: false, updater_initialized: false",
        "Rust shell initialization",
    )
    marker = "        updater::show_ui(ui.ctx(), &self.app, &mut self.updater_open, &mut self.updater_initialized);"
    if marker not in rust:
        pat = (r"(    fn ui\\(&mut self, ui: &mut egui::Ui, frame: &mut eframe::Frame\\) \\{\\n)"
               r"(.*?)"
               r"(\\n    \\}\\n\\n    fn raw_input_hook)")
        match = re.search(pat, rust, re.DOTALL)
        if match is None:
            raise RuntimeError("Could not locate egui shell UI hook")
        rust = rust[:match.start()] + match.group(1) + match.group(2) + (
            "\n" + marker
        ) + match.group(3) + rust[match.end():]

    # Validate all in memory BEFORE updating any generated files.
    if "__" in updater_rust:
        raise RuntimeError("Unresolved Rust updater placeholder")
    if "__PACKAGE__" in updater_java:
        raise RuntimeError("Unresolved Java updater placeholder")
    if "mod updater;" not in rust or marker not in rust:
        raise RuntimeError("Rust updater hook absent")
    manifest_path.write_text(manifest)
    activity_path.write_text(activity_text)
    (java_dir / "ArtCraftUpdater.java").write_text(updater_java)
    (android_dir / "src" / "updater.rs").write_text(updater_rust)
    lib_path.write_text(rust)
    print(f"Installed opt-in updater for {app}: {TARGET_TAG[app]} (package {java_package})")


if __name__ == "__main__":
    main()
