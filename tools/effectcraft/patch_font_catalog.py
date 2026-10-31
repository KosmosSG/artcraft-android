"""Add lazy, deduplicated Android file registration to the pinned text engine."""
from pathlib import Path

API = r'''
/// Android bridge: parse names now and load glyph data only when used.
/// Existing IDs remain valid; duplicate family/style pairs reuse existing faces.
pub fn android_add_font_file(path: &std::path::Path) -> Vec<FaceId> {
    let Ok(mut file) = std::fs::File::open(path) else { return Vec::new() };
    let Ok(meta) = file.metadata() else { return Vec::new() };
    if !meta.is_file() || meta.len() < 12 || meta.len() > 64 * 1024 * 1024 {
        return Vec::new();
    }
    let names = read_faces(&mut file);
    let mut d = db().write().unwrap_or_else(|e| e.into_inner());
    let mut ids = Vec::new();
    for n in names {
        let info = info_from(n, FaceData::File(path.to_owned()), "android");
        let existing = d.faces.iter().find(|f|
            f.info.family.eq_ignore_ascii_case(&info.family)
            && f.info.style.eq_ignore_ascii_case(&info.style)).map(|f| f.id);
        ids.push(existing.unwrap_or_else(|| push(&mut d, info)));
    }
    drop(d);
    family_faces_cache().write().unwrap_or_else(|e| e.into_inner()).clear();
    ids
}
'''
TESTS = r'''
#[cfg(test)]
mod android_catalog_tests {
    use super::*;
    #[test]
    fn file_registration_resolves_family_and_deduplicates() {
        let p = std::env::temp_dir().join(format!("effectcraft-android-{}.ttf", std::process::id()));
        std::fs::write(&p, INTER_REGULAR).unwrap();
        let a = android_add_font_file(&p);
        assert!(!a.is_empty());
        assert_eq!(a, android_add_font_file(&p));
        assert!(families().iter().any(|(family, _)| family == "Inter"));
        assert!(!resolve("Inter", "Regular").missing);
        std::fs::write(&p, b"invalid font data").unwrap();
        assert!(android_add_font_file(&p).is_empty());
        std::fs::remove_file(p).unwrap();
    }
    #[test]
    fn ttc_collection_registers_and_resolves_real_families() {
        let path = std::env::var_os("EFFECTCRAFT_TEST_TTC").expect("CI supplies real TTC fixture");
        let ids = android_add_font_file(std::path::Path::new(&path));
        assert!(ids.len() >= 2);
        for id in ids {
            let f = face(id);
            assert!(families().iter().any(|(name, _)| name == &f.info.family));
            assert!(!resolve(&f.info.family, &f.info.style).missing);
            assert!(f.font().is_some());
        }
    }
}
'''

def apply(root):
    p = Path(root) / 'crates/text/src/fonts.rs'
    s = p.read_text()
    anchor = '/// Held for a whole system scan:'
    if s.count(anchor) != 1 or 'pub fn android_add_font_file' in s:
        raise SystemExit('STOP: pinned font catalog source drift')
    p.write_text(s.replace(anchor, API + '\n' + anchor, 1) + TESTS)

if __name__ == '__main__':
    import sys
    apply(sys.argv[1])
