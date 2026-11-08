#!/usr/bin/env python3
"""Preserve the published DesignCraft Android updater on pinned upstream v0.17.

Run AFTER patch_v017_android.py has installed the existing SAF/font/keyboard
overlays. This only modifies the generated DesignCraft checkout, not other apps.
Every source anchor is checked exactly once to fail closed on upstream drift.
"""
from pathlib import Path
import sys
import tomllib


def once(text: str, old: str, new: str, where: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{where}: expected one anchor, found {count}: {old[:100]!r}")
    return text.replace(old, new, 1)


def edit(path: Path, before: str, after: str) -> None:
    path.write_text(once(path.read_text(), before, after, str(path)))


def apply(root: Path, src: Path, android: Path) -> None:
    if src.name != "designcraft" or android.name != "designcraft-android":
        raise ValueError("DesignCraft-only upstream updater patch")
    support = root / "tools/designcraft/support"
    manifest = tomllib.loads((android / "Cargo.toml").read_text())
    package = manifest["package"]["metadata"]["android"]["package"]
    if package not in ("com.artcraft.designcraft.test", "com.artcraft.designcraft"):
        raise ValueError("Unexpected DesignCraft Android application identity")

    ui_root = src / "crates/ui-egui/src"
    command_file = ui_root / "menus/ui_commands.rs"
    edit(command_file,
         '    ("app.artcraftImportFont", "Import Fonts (TTF/OTF/TTC)…", None, "{}"),',
         '    ("app.artcraftImportFont", "Import Fonts (TTF/OTF/TTC)…", None, "{}"),\n'
         '    #[cfg(target_os = "android")]\n'
         '    ("app.artcraftCheckUpdates", "Check updates", None, "{}"),\n'
         '    #[cfg(target_os = "android")]\n'
         '    ("app.artcraftStartupCheck", "Startup update check", None, "{}"),')

    run_file = ui_root / "menus/run.rs"
    edit(run_file,
         'static ANDROID_SHARED_ACTIONS: std::sync::atomic::AtomicU8 =',
         '''static ANDROID_UPDATE_ACTION: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
pub fn take_android_update_action() -> u8 {
    ANDROID_UPDATE_ACTION.swap(0, std::sync::atomic::Ordering::Relaxed)
}
#[cfg(target_os = "android")]
static ANDROID_SHARED_ACTIONS: std::sync::atomic::AtomicU8 =''')
    edit(run_file,
         '    if id == "app.artcraftToggleAndroidTools" {',
         '''    if id == "app.artcraftCheckUpdates" {
        ANDROID_UPDATE_ACTION.store(3, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
    if id == "app.artcraftStartupCheck" {
        ANDROID_UPDATE_ACTION.store(4, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
    if id == "app.artcraftToggleAndroidTools" {''')

    menu_file = ui_root / "menus.rs"
    edit(menu_file,
         'pub use run::{take_android_font_import, take_android_shared_actions, take_android_tools_toggle};',
         'pub use run::{take_android_font_import, take_android_shared_actions, take_android_tools_toggle, take_android_update_action};')
    # Android.2 consolidates actions under the user-approved top-left Dc icon.
    # Do not reinsert update controls into the removed top-level Android menu.
    # Native dc_update_action() below powers both Dc dropdown actions.
    table_file = ui_root / "menus/tables.rs"
    table_source = table_file.read_text()
    if '"Android",\n' in table_source or '"ui:app.artcraftToggleAndroidTools"' in table_source:
        raise ValueError("Unexpected old Android top-level menu; review before patching")
    dc_menu = (ui_root / "menus/bar.rs").read_text()
    for label in ("dc-launcher-icon.rgba", "Check Updates", "Startup Update Check",
                  "Import Fonts", "Choose Shared Font Folder", "Refresh Shared Fonts",
                  "Reload Font Catalog", "Font Catalog & Diagnostics",
                  "App Updates", "Appearance", "DesignCraft Shortcuts",
                  "About DesignCraft"):
        if label not in dc_menu:
            raise ValueError(f"Missing approved Dc launcher menu action: {label}")


    bridge_file = android / "src/lib.rs"
    edit(bridge_file,
         '        pub fn dc_tool_action(&self) -> Result<i32, String> {',
         '''        pub fn dc_update_action(&self, action: i64) -> Result<(), String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcAction"), jni_sig!("(J)V"),
                    &[JValue::Long(action)])?;
                Ok(())
            }).map_err(|e| e.to_string())
        }

        pub fn dc_tool_action(&self) -> Result<i32, String> {''')

    toolbar_file = android / "src/v016_android.rs"
    edit(toolbar_file,
         '    let shared_actions = designcraft_ui_egui::menus::take_android_shared_actions();',
         '''    let update_action = designcraft_ui_egui::menus::take_android_update_action();
    if update_action != 0 {
        if let Err(error) = bridge.dc_update_action(update_action as i64) {
            app.status_error("DesignCraft updates", error);
        }
    }
    let shared_actions = designcraft_ui_egui::menus::take_android_shared_actions();''')
    # Android.2 already routes both update actions from the top-left Dc menu.
    # The legacy Android Tools toolbar is intentionally absent; check the
    # action/bridge contract instead of trying to reinsert duplicate buttons.
    dc_native = toolbar_file.read_text()
    for action, code in (('Check Updates', 'bridge.dc_update_action(3)'),
                         ('Startup Update Check', 'bridge.dc_update_action(4)')):
        if dc_menu.count(action) != 1 or dc_native.count(code) != 1:
            raise ValueError(f"Dc app-bar updater action not wired exactly once: {action}")


    java_dir = android / "java" / Path(*package.split("."))
    java_file = java_dir / "DesignCraftActivity.java"
    java = java_file.read_text()
    for name in ("java.io.InputStream", "java.util.concurrent.ExecutorService",
                 "java.util.concurrent.Executors", "org.json.JSONArray", "org.json.JSONObject"):
        statement = f"import {name};"
        if statement not in java:
            java = once(java, f"package {package};\n",
                        f"package {package};\n{statement}\n", str(java_file))
    java = once(java, '        dcRestoreSharedFontsOnStartup();',
                '''        dcRestoreSharedFontsOnStartup();
        if (getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean("dc_startup_check", false)) {
            dcCheckUpdates(false);
        }''', str(java_file))
    methods = (support / "update_methods.java").read_text()
    if "void dcAction(long action)" not in methods:
        raise ValueError("Published DesignCraft updater method missing")
    terminator = java.rfind("\n}")
    if terminator < 0 or "void dcAction(long action)" in java:
        raise ValueError("Cannot safely insert DesignCraft updater")
    java_file.write_text(java[:terminator] + "\n" + methods + "\n" + java[terminator:])

    policy_file = java_dir / "DesignCraftUpdatePolicy.java"
    original_policy = (support / "DesignCraftUpdatePolicy.java").read_text()
    original_policy = once(original_policy, "package com.artcraft.designcraft;",
                           f"package {package};", str(policy_file))
    if policy_file.exists():
        raise ValueError("Existing updater policy file must not be overwritten")
    policy_file.write_text(original_policy)
    print("DesignCraft v0.17: preserved published read-only updater and startup controls")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: install_v017_updater.py ROOT SOURCE ANDROID")
    apply(*(Path(p).resolve() for p in sys.argv[1:]))
