"""Stage Android-specific Type / Help menu integration into the reviewed source checkout."""
from pathlib import Path

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("DesignCraft menu API drift: " + old[:70])
    return text.replace(old, new)

def apply(path: Path):
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
            // Keep upstream menu order and append a separated Android-only section.
            // About DesignCraft is a dialog action; update controls follow it in Help.
            if !entries.is_empty() && !matches!(entries.last(), Some(Item::Sep)) {
                entries.push(Item::Sep);
            }
            entries.extend(ids.iter().map(|id| cmd_item(id, Value::Null)));
        }
    }
    tree
}""")
    path.write_text(text)

if __name__ == "__main__":
    import sys
    apply(Path(sys.argv[1]))

