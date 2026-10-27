// Opt-in PhotoCraft compatibility for a keyboard reporting Esc as Android Back.
// The observed HONOR keyboard sends AKEYCODE_BACK with Linux KEY_BACK (158).
// Require a keyboard source and the observed scan code: gesture/soft Back stays Back.
pub(crate) fn keyboard_back_is_escape(code: i32, scan: i32, source: i32) -> bool {
    const ANDROID_BACK: i32 = 4;
    const LINUX_KEY_BACK: i32 = 158;
    const SOURCE_KEYBOARD: i32 = 0x101;
    code == ANDROID_BACK && scan == LINUX_KEY_BACK
        && source & SOURCE_KEYBOARD == SOURCE_KEYBOARD
}

#[cfg(test)]
mod tests {
    use super::keyboard_back_is_escape as maps;
    #[test]
    fn observed_keyboard_back_maps() {
        assert!(maps(4, 158, 0x101));
        assert!(maps(4, 158, 0x301)); // combined keyboard sources
    }
    #[test]
    fn navigation_and_other_keys_are_unchanged() {
        assert!(!maps(4, 0, 0x101)); // software Back
        assert!(!maps(4, 158, 0x1002)); // touchscreen
        assert!(!maps(4, 158, 0x201)); // directional controller
        assert!(!maps(4, 1, 0x101)); // unobserved scan code
        for key in [111, 31, 42, 53, 50, 48] { // Esc, C/N/Y/V/T
            assert!(!maps(key, 158, 0x101));
        }
    }
}
