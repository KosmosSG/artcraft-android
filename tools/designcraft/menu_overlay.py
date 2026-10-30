"""Stage Android-specific Type / Help menu integration into the reviewed source checkout."""
from pathlib import Path

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("DesignCraft menu API drift: " + old[:70])
    return text.replace(old, new)

def apply(path: Path):
    if path.is_dir():
        return apply_modular(path)
    text = path.read_text()
    text = replace_once(text,
        'pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[',
        '''pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[
    #[cfg(target_os = "android")]
    ("app.artcraftImportFont", "Custom Font Import (TTF/OTF)…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftSelectSharedFonts", "Select Shared Font Folder…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftRefreshSharedFonts", "Refresh Shared Fonts", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftCheckUpdates", "Check for Updates…", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftUpdateSettings", "Startup Update Settings…", None, "{}"),
    #[cfg(target_os = "android")]
    ("window.artcraftShortcutPad", "Toggle Touch Shortcut Pad", None, "{}"),''')
    text = replace_once(text, 'pub fn ui_label(id: &str) -> Option<(&',
        '''#[cfg(target_os = "android")]
static ARTCRAFT_ANDROID_ACTIONS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);

#[cfg(target_os = "android")]
pub fn artcraft_take_android_actions() -> u32 {
    ARTCRAFT_ANDROID_ACTIONS.swap(0, std::sync::atomic::Ordering::Relaxed)
}

pub fn ui_label(id: &str) -> Option<(&''')
    text = replace_once(text,
        '    Some(match id {\n        "window.minimize" => {',
        '''    Some(match id {
        #[cfg(target_os = "android")]
        "app.artcraftImportFont" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(1, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftSelectSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(2, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftRefreshSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(4, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftCheckUpdates" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(8, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftUpdateSettings" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(16, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "window.artcraftShortcutPad" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(32, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        "window.minimize" => {''')
    text = replace_once(text,
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect()
}""",
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    let mut tree: Vec<(&'static str, Vec<Item>)> =
        MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect();
    #[cfg(target_os = "android")]
    for (menu, entries) in &mut tree {
        let ids: &[&str] = match *menu {
            "Type" => &["app.artcraftImportFont", "app.artcraftSelectSharedFonts", "app.artcraftRefreshSharedFonts"],
            "Help" => &["help.artcraftCheckUpdates", "help.artcraftUpdateSettings"],
            "Window" => &["window.artcraftShortcutPad"],
            _ => &[],
        };
        if !ids.is_empty() {
            let mut android: Vec<Item> = ids.iter().map(|id| cmd_item(id, Value::Null)).collect();
            android.push(Item::Sep);
            entries.splice(0..0, android);
        }
    }
    tree
}""")
    path.write_text(text)


def apply_modular(directory: Path):
    """Port only the reviewed v0.14 split menu modules; reject any unexpected layout."""
    ui_path = directory / "ui_commands.rs"
    run_path = directory / "run.rs"
    tree_path = directory / "tree.rs"
    mod_path = directory.parent / "menus.rs"
    if not all(p.is_file() for p in (ui_path, run_path, tree_path, mod_path)):
        raise ValueError("DesignCraft modular menu layout incomplete; review required")
    ui = ui_path.read_text()
    ui = replace_once(ui,
        'pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[',
        '''pub const UI_COMMANDS: &[(&str, &str, Option<&str>, &str)] = &[
    #[cfg(target_os = "android")]
    ("app.artcraftImportFont", "Custom Font Import (TTF/OTF)…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftSelectSharedFonts", "Select Shared Font Folder…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftRefreshSharedFonts", "Refresh Shared Fonts", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftCheckUpdates", "Check for Updates…", None, "{}"),
    #[cfg(target_os = "android")]
    ("help.artcraftUpdateSettings", "Startup Update Settings…", None, "{}"),
    #[cfg(target_os = "android")]
    ("window.artcraftShortcutPad", "Toggle Touch Shortcut Pad", None, "{}"),''')
    run = run_path.read_text()
    run = replace_once(run, 'pub fn run_ui(app: &mut DesignApp, id: &str, p: &Value)',
        '''#[cfg(target_os = "android")]
static ARTCRAFT_ANDROID_ACTIONS: std::sync::atomic::AtomicU32 =
    std::sync::atomic::AtomicU32::new(0);

#[cfg(target_os = "android")]
pub fn artcraft_take_android_actions() -> u32 {
    ARTCRAFT_ANDROID_ACTIONS.swap(0, std::sync::atomic::Ordering::Relaxed)
}

pub fn run_ui(app: &mut DesignApp, id: &str, p: &Value)''')
    run = replace_once(run, '    Some(match id {\n        "window.minimize" => {',
        '''    Some(match id {
        #[cfg(target_os = "android")]
        "app.artcraftImportFont" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(1, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftSelectSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(2, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "app.artcraftRefreshSharedFonts" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(4, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftCheckUpdates" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(8, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "help.artcraftUpdateSettings" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(16, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        #[cfg(target_os = "android")]
        "window.artcraftShortcutPad" => { ARTCRAFT_ANDROID_ACTIONS.fetch_or(32, std::sync::atomic::Ordering::Relaxed); Ok(Value::Null) }
        "window.minimize" => {''')
    tree = tree_path.read_text()
    tree = replace_once(tree,
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect()
}""",
        """pub fn menu_tree() -> Vec<(&'static str, Vec<Item>)> {
    let mut tree: Vec<(&'static str, Vec<Item>)> =
        MENUS.iter().map(|(m, e)| (*m, parse_entries(e))).collect();
    #[cfg(target_os = "android")]
    for (menu, entries) in &mut tree {
        let ids: &[&str] = match *menu {
            "Type" => &["app.artcraftImportFont", "app.artcraftSelectSharedFonts", "app.artcraftRefreshSharedFonts"],
            "Help" => &["help.artcraftCheckUpdates", "help.artcraftUpdateSettings"],
            "Window" => &["window.artcraftShortcutPad"],
            _ => &[],
        };
        if !ids.is_empty() {
            let mut android: Vec<Item> = ids.iter().map(|id| cmd_item(id, Value::Null)).collect();
            android.push(Item::Sep);
            entries.splice(0..0, android);
        }
    }
    tree
}""")
    mod = replace_once(mod_path.read_text(), 'pub use run::run_ui;',
        '''pub use run::run_ui;
#[cfg(target_os = "android")]
pub use run::artcraft_take_android_actions;''')
    # Write only after every pinned anchor has passed; no partial modifications.
    for path, content in ((ui_path, ui), (run_path, run), (tree_path, tree), (mod_path, mod)):
        path.write_text(content)

if __name__ == "__main__":
    import sys
    apply(Path(sys.argv[1]))

