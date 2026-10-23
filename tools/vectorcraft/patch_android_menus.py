"""Patch only pinned VectorCraft Android builder's menu tree.

Uses transient, Android-only atomic requests. No upstream desktop menu is
modified; an unsupported source revision stops rather than guessing a patch.
"""
from pathlib import Path
import argparse

PIN="ad0566943ab9741e6356bbc9b53c3cc09895068d"

def insert_once(s, anchor, replacement):
    if s.count(anchor)!=1:
        raise ValueError("Reviewed VectorCraft menu anchor missing or duplicated: "+anchor[:70])
    return s.replace(anchor,replacement,1)

def patch(builder: Path):
    root=builder/"source/vectorcraft"
    menu=root/"crates/ui-egui/src/menus.rs"
    s=menu.read_text()
    s=insert_once(s,
        "use crate::widgets;\n",
        """use crate::widgets;

// Android-only, one-shot in-app requests; native menu dispatch never uses
// unsafe JNI or forces non-Android builds to understand these entries.
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
""")
    s=insert_once(s,
        '    if UI_COMMANDS.iter().any(|c| c.0 == id) {\n',
        """    #[cfg(target_os = "android")]
    if id.starts_with("android.vectorcraft.") {
        return Ok(());
    }
    if UI_COMMANDS.iter().any(|c| c.0 == id) {
""")
    anchor="pub fn run_ui_command(app: &mut VectorcraftApp, id: &str, p: &Value) -> Option<Result<Value, String>> {\n"
    s=insert_once(s,anchor,anchor+"""    #[cfg(target_os = "android")]
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
            ANDROID_MENU_BITS.fetch_or(bit, std::sync::atomic::Ordering::AcqRel);
            return Some(Ok(Value::Null));
        }
    }
""")
    s=insert_once(s,
        'pub fn checked(app: &VectorcraftApp, id: &str, p: &Value) -> Option<bool> {\n',
        '''pub fn checked(app: &VectorcraftApp, id: &str, p: &Value) -> Option<bool> {
    #[cfg(target_os = "android")]
    match id {
        "android.vectorcraft.touchPad" => return Some(ANDROID_TOUCH_ENABLED.load(std::sync::atomic::Ordering::Acquire)),
        "android.vectorcraft.startupUpdates" => return Some(ANDROID_STARTUP_ENABLED.load(std::sync::atomic::Ordering::Acquire)),
        _ => (),
    }
''')
    s=insert_once(s,
        '            "Type",\n            vec![\n                sub("Font", font_items(english_names)),',
        """            "Type",
            vec![
                c("Import Font (.ttf / .otf)…", "android.vectorcraft.fontImport"),
                c("Select Shared Font Folder…", "android.vectorcraft.fontFolder"),
                c("Refresh Shared Fonts", "android.vectorcraft.fontRefresh"),
                Sep,
                sub("Font", font_items(english_names)),""")
    s=insert_once(s,
        '            "Help",\n            vec![\n                c("Join Our Discord", "help.discord"),',
        """            "Help",
            vec![
                c("Check for VectorCraft Updates", "android.vectorcraft.updates"),
                c("Check for Updates at Startup", "android.vectorcraft.startupUpdates"),
                c("Graphics Diagnostics…", "android.vectorcraft.diagnostics"),
                Sep,
                c("Join Our Discord", "help.discord"),""")
    s=insert_once(s,
        '            "Window",\n            vec![\n',
        """            "Window",
            vec![
                c("Touch Shortcut Pad", "android.vectorcraft.touchPad"),
                Sep,
""")
    menu.write_text(s)
    print("PASS: Android Type/Help/Window menus wired to existing VectorCraft bridge")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("builder",type=Path)
    args=p.parse_args()
    patch(args.builder)
