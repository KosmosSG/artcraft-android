"""VectorCraft v0.20.0-only Android menu overlay.

Official v0.20 splits menus.rs into run/state/tree modules. Port the existing
v0.14 Android command bridge to those modules without removing upstream menu
commands. Every reviewed source anchor must occur exactly once or this fails
closed rather than producing a partially working Android app.
"""
from pathlib import Path
import argparse

SUPPORTED_VERSIONS = ('version = "0.20.0"', 'version = "0.21.0"')


def insert_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"Unreviewed v0.20 VectorCraft {label} anchor (expected once, found {source.count(old)})")
    return source.replace(old, new, 1)


def patch(builder: Path) -> None:
    upstream = builder / "source/vectorcraft"
    manifest = (upstream / "Cargo.toml").read_text()
    if sum(manifest.count(v) for v in SUPPORTED_VERSIONS) != 1:
        raise RuntimeError("Only reviewed upstream VectorCraft v0.20.0 or v0.21.0 is supported")
    root = upstream / "crates/ui-egui/src"
    menus = root / "menus.rs"
    run = root / "menus/run.rs"
    state = root / "menus/state.rs"
    tree = root / "menus/tree.rs"

    # Root module owns Android-only one-shot command routing and checked state.
    s = menus.read_text()
    s = insert_once(s, "use crate::widgets;\n", """use crate::widgets;

// Android-only one-shot requests polled by the existing production shell.
#[cfg(target_os = "android")]
static ANDROID_MENU_BITS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);
#[cfg(target_os = "android")]
static ANDROID_TOUCH_ENABLED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
static ANDROID_STARTUP_ENABLED: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "android")]
pub fn set_android_preferences(touch: bool, startup: bool) {
    use std::sync::atomic::Ordering::Release;
    ANDROID_TOUCH_ENABLED.store(touch, Release);
    ANDROID_STARTUP_ENABLED.store(startup, Release);
}
#[cfg(target_os = "android")]
pub fn take_android_menu_bits() -> u32 {
    ANDROID_MENU_BITS.swap(0, std::sync::atomic::Ordering::AcqRel)
}
""", "Android menu bridge imports")

    srun = run.read_text()
    srun = insert_once(srun,
        '    if UI_COMMANDS.iter().any(|c| c.0 == id) {\n',
        '''    #[cfg(target_os = "android")]
    if id.starts_with("android.vectorcraft.") {
        return Ok(());
    }
    if UI_COMMANDS.iter().any(|c| c.0 == id) {
''', "Android UI command parameters")
    anchor = 'pub fn run_ui_command(app: &mut VectorcraftApp, id: &str, p: &Value) -> Option<Result<Value, String>> {\n'
    srun = insert_once(srun, anchor, anchor + '''    #[cfg(target_os = "android")]
    {
        let bit = match id {
            "android.vectorcraft.fontImport" => 1,
            "android.vectorcraft.fontFolder" => 2,
            "android.vectorcraft.fontRefresh" => 4,
            "android.vectorcraft.updates" => 8,
            "android.vectorcraft.startupUpdates" => 16,
            "android.vectorcraft.touchPad" => 32,
            "android.vectorcraft.diagnostics" => 64,
            _ => 0,
        };
        if bit != 0 {
            super::ANDROID_MENU_BITS.fetch_or(bit, std::sync::atomic::Ordering::AcqRel);
            return Some(Ok(Value::Null));
        }
    }
''', "Android UI command routing")

    sstate = state.read_text()
    anchor = 'pub fn checked(app: &VectorcraftApp, id: &str, p: &Value) -> Option<bool> {\n'
    sstate = insert_once(sstate, anchor, anchor + '''    #[cfg(target_os = "android")]
    match id {
        "android.vectorcraft.touchPad" => return Some(super::ANDROID_TOUCH_ENABLED.load(std::sync::atomic::Ordering::Acquire)),
        "android.vectorcraft.startupUpdates" => return Some(super::ANDROID_STARTUP_ENABLED.load(std::sync::atomic::Ordering::Acquire)),
        _ => (),
    }
''', "Android toggles")

    stree = tree.read_text()
    stree = insert_once(stree,
        '                sub("Type Orientation", vec![c("Horizontal", "type.orientation.horizontal"), c("Vertical", "type.orientation.vertical")]),\n            ],\n        ),\n        ("Select", {',
        '''                sub("Type Orientation", vec![c("Horizontal", "type.orientation.horizontal"), c("Vertical", "type.orientation.vertical")]),
                #[cfg(target_os = "android")]
                Sep,
                #[cfg(target_os = "android")]
                c("Import Font (.ttf / .otf)…", "android.vectorcraft.fontImport"),
                #[cfg(target_os = "android")]
                c("Select Shared Font Folder…", "android.vectorcraft.fontFolder"),
                #[cfg(target_os = "android")]
                c("Refresh Shared Fonts", "android.vectorcraft.fontRefresh"),
            ],
        ),
        ("Select", {''', "Type font menu")
    # Window has become an inline builder. Keep its existing upstream items.
    stree = insert_once(stree,
        '''        ("Window", {
            let mut window_items = vec![
                c("New Window", "window.newWindow"),''',
        '''        ("Window", {
            let mut window_items = vec![
                #[cfg(target_os = "android")]
                c("Touch Shortcut Pad", "android.vectorcraft.touchPad"),
                #[cfg(target_os = "android")]
                Sep,
                c("New Window", "window.newWindow"),''', "Window touch menu")
    stree = insert_once(stree,
        '''            "Help",
            vec![
                c("Join Our Discord", "help.discord"),''',
        '''            "Help",
            vec![
                #[cfg(target_os = "android")]
                c("Graphics Diagnostics…", "android.vectorcraft.diagnostics"),
                #[cfg(target_os = "android")]
                Sep,
                c("Join Our Discord", "help.discord"),''', "Help diagnostics")
    # v0.20 has a built-in official upstream updater; do not duplicate this UI
    # on Android. Keep upstream's own updater on desktop and add our Android
    # release-filtered controls under About where the existing shell expects.
    stree = insert_once(stree,
        '''                c("Check for Updates…", "help.checkForUpdates"),
                c("About VectorCraft", "help.about"),
            ],
        ),
    ]''',
        '''                #[cfg(not(target_os = "android"))]
                c("Check for Updates…", "help.checkForUpdates"),
                c("About VectorCraft", "help.about"),
                #[cfg(target_os = "android")]
                c("Check for VectorCraft Updates", "android.vectorcraft.updates"),
                #[cfg(target_os = "android")]
                c("Check for Updates at Startup", "android.vectorcraft.startupUpdates"),
            ],
        ),
    ]''', "Help update controls")

    # Match the reviewed PhotoCraft Android menu's input policy:
    # allow touch dragging and two-finger wheel gestures within menu ScrollAreas.
    # Keep upstream scrolling inertia and nested popups; do not hijack Android
    # system gestures or rewrite motion events globally.
    dropdowns = root / "widgets/dropdowns.rs"
    dropdowns_src = dropdowns.read_text()
    dropdowns_src = insert_once(dropdowns_src,
        'egui::ScrollArea::vertical().max_height(room).min_scrolled_height(room).show(ui, add_contents).inner',
        'egui::ScrollArea::vertical().scroll_source(egui::containers::scroll_area::ScrollSource::ALL).max_height(room).min_scrolled_height(room).show(ui, add_contents).inner',
        "menu scroll source (touch drag + wheel)")

    # Validate all replacement targets BEFORE writing any source.
    for modified, marker in ((s, "ANDROID_MENU_BITS"),
                             (srun, "super::ANDROID_MENU_BITS"),
                             (sstate, "super::ANDROID_TOUCH_ENABLED"),
                             (stree, "android.vectorcraft.fontImport")):
        if marker not in modified:
            raise RuntimeError(f"Android overlay missing required marker {marker}")
    for path, source in ((menus, s), (run, srun), (state, sstate), (tree, stree), (dropdowns, dropdowns_src)):
        path.write_text(source)
    print("PASS: reviewed v0.20 Type/Help/Window Android controls and one-shot bridge")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    patch(parser.parse_args().builder)
