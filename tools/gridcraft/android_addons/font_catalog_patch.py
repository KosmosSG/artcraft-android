"""Reviewed transformations of the pinned GridCraft font catalog; Android checkout only."""
def once(s, old, new):
    if s.count(old) != 1:
        raise RuntimeError(f'Pinned GridCraft font API changed: {old!r}')
    return s.replace(old, new, 1)

def patch_catalog(s):
    s = once(s, 'static CATALOG: OnceLock<Vec<Face>> = OnceLock::new();', '''// GRIDCRAFT_RELOADABLE_CATALOG_V1: readers retain an immutable snapshot.
static CATALOG: OnceLock<std::sync::RwLock<std::sync::Arc<Vec<Face>>>> = OnceLock::new();
static GENERATION: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
pub fn generation() -> u64 { GENERATION.load(std::sync::atomic::Ordering::Acquire) }
/// Called on the Android font worker only, after Java commits the font cache.
pub fn reload_catalog() {
    let fresh = scan_dirs(&system_font_dirs());
    let cache = CATALOG.get_or_init(|| std::sync::RwLock::new(std::sync::Arc::new(Vec::new())));
    *cache.write().unwrap_or_else(|e| e.into_inner()) = std::sync::Arc::new(fresh);
    GENERATION.fetch_add(1, std::sync::atomic::Ordering::Release);
}''')
    s = once(s, '''pub fn catalog() -> &'static [Face] {
    CATALOG.get_or_init(|| scan_dirs(&system_font_dirs()))
}''', '''pub fn catalog() -> std::sync::Arc<Vec<Face>> {
    CATALOG.get_or_init(|| std::sync::RwLock::new(std::sync::Arc::new(scan_dirs(&system_font_dirs()))))
        .read().unwrap_or_else(|e| e.into_inner()).clone()
}''')
    s = once(s, '''fn catalog_now() -> Option<&'static [Face]> {
    CATALOG.get().map(Vec::as_slice)
}''', '''fn catalog_now() -> Option<std::sync::Arc<Vec<Face>>> {
    CATALOG.get().map(|cache| cache.read().unwrap_or_else(|e| e.into_inner()).clone())
}''')
    s = once(s, 'faces_named(cat, family)', 'faces_named(&cat, family)')
    s = once(s, 'installed_in(cat, names)', 'installed_in(&cat, names)')
    return s

def patch_app(s):
    s = once(s, '    fonts_seen: (u64, u64),', '    fonts_seen: (u64, u64),\n    android_font_generation: u64,')
    s = once(s, '            fonts_seen: (0, 0),', '            fonts_seen: (0, 0),\n            android_font_generation: 0,')
    s = once(s, '            if seen != self.fonts_seen {', '''            let generation = fonts::generation();
            let catalog_changed = generation != self.android_font_generation;
            self.android_font_generation = generation;
            if catalog_changed || seen != self.fonts_seen {''')
    s = once(s, '                if used != self.fonts_bound {', '                if catalog_changed || used != self.fonts_bound {')
    return s
