//! Android menu requests consumed by the builder-owned JNI shell.
//! No Android dependency: the request bridge is also exercised on the host.
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

pub const IMPORT_FONT: u32 = 1;
pub const SELECT_FONT_FOLDER: u32 = 2;
pub const REFRESH_FONTS: u32 = 4;
pub const CHECK_UPDATES: u32 = 8;
pub const TOGGLE_STARTUP: u32 = 16;
pub const ANDROID_SETTINGS: u32 = 32;
static REQUESTS: AtomicU32 = AtomicU32::new(0);
static STARTUP: AtomicBool = AtomicBool::new(false);

fn action(id: &str) -> Option<u32> {
    match id {
        "android.importFont" => Some(IMPORT_FONT),
        "android.selectFontFolder" => Some(SELECT_FONT_FOLDER),
        "android.refreshFonts" => Some(REFRESH_FONTS),
        "android.checkUpdates" => Some(CHECK_UPDATES),
        "android.startupUpdates" => Some(TOGGLE_STARTUP),
        "android.settings" => Some(ANDROID_SETTINGS),
        _ => None,
    }
}

pub fn is_command(id: &str) -> bool { action(id).is_some() }

pub fn request(id: &str) -> bool {
    let Some(flag) = action(id) else { return false };
    // Coalesce duplicate picker/check requests; a toggle is parity-sensitive.
    if flag == TOGGLE_STARTUP {
        REQUESTS.fetch_xor(flag, Ordering::AcqRel);
    } else {
        REQUESTS.fetch_or(flag, Ordering::AcqRel);
    }
    true
}

pub fn take() -> u32 { REQUESTS.swap(0, Ordering::AcqRel) }
pub fn set_startup(enabled: bool) { STARTUP.store(enabled, Ordering::Release); }
pub fn checked(id: &str) -> Option<bool> {
    (id == "android.startupUpdates").then(|| STARTUP.load(Ordering::Acquire))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn menu_requests_reach_shell_once_and_preserve_toggle_parity() {
        assert_eq!(take(), 0);
        for (id, flag) in [
            ("android.importFont", IMPORT_FONT),
            ("android.selectFontFolder", SELECT_FONT_FOLDER),
            ("android.refreshFonts", REFRESH_FONTS),
            ("android.checkUpdates", CHECK_UPDATES),
            ("android.settings", ANDROID_SETTINGS),
        ] {
            assert!(is_command(id));
            assert!(request(id));
            assert!(request(id));
            assert_eq!(take(), flag);
            assert_eq!(take(), 0);
        }
        assert!(!request("file.open"));
        assert_eq!(take(), 0);
        set_startup(true);
        assert_eq!(checked("android.startupUpdates"), Some(true));
        set_startup(false);
        assert_eq!(checked("android.startupUpdates"), Some(false));
        assert_eq!(checked("android.importFont"), None);
        request("android.startupUpdates");
        request("android.startupUpdates");
        assert_eq!(take(), 0);
        request("android.startupUpdates");
        assert_eq!(take(), TOGGLE_STARTUP);
    }
}
