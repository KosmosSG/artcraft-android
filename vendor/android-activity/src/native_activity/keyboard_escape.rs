// Opt-in PhotoCraft compatibility: the observed HONOR Esc is Android Back,
// Linux KEY_BACK (158). Match that hardware pair regardless of OEM/IME source
// classification. Software/gesture Back (scan 0) and other keys stay unchanged.
pub(crate) fn keyboard_back_is_escape(code: i32, scan: i32, _source: i32) -> bool {
    code == 4 && scan == 158
}

#[cfg(test)]
mod tests {
    use super::keyboard_back_is_escape as maps;
    #[test]
    fn observed_hardware_pair_survives_source_classification() {
        for source in [0, 0x101, 0x301, 0x201, 0x1002] {
            assert!(maps(4, 158, source));
        }
    }
    #[test]
    fn software_back_and_other_keys_are_unchanged() {
        for source in [0, 0x101, 0x301, 0x201, 0x1002] {
            assert!(!maps(4, 0, source));
            assert!(!maps(4, 1, source));
            for key in [111, 31, 42, 53, 50, 48] { // Esc, C/N/Y/V/T
                assert!(!maps(key, 158, source));
            }
        }
    }
}
