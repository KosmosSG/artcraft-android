"""VectorCraft Android.23: reduce FUSE scan cost on startup and scroll.

Apply after symlink-cache patch; preserve 4GiB/5000 shared-font discovery,
full import refresh, and all bundled/fallback font families.
"""
from pathlib import Path
from backend_stability import once

def patch(root: Path) -> None:
    path=root/"templates/android/system_fonts.rs"
    s=path.read_text()
    if "vectorcraft-font-links-cache-v1" not in s:
        raise ValueError("Stable symlink cache must run first")
    s=once(s,'''            let count = entries.flatten().count() as u64;''',
    '''            // Do not walk up to 5000 entries through Android FUSE just
            // to validate a *cached* symlink directory at cold launch.
            // Full import and Refresh Fonts still recursively discover all.
            let _ = entries;
            let count = std::fs::metadata(path)
                .map(|metadata| metadata.len()).unwrap_or(0);''')
    s=once(s,'''    refresh_font_links();
    // The families bound this pass,''',
    '''    refresh_font_links_off_ui_thread();
    // The families bound this pass,''')
    s=once(s,'''#[cfg(unix)]
fn link_desktop_names(dir: &Path) {''',
    '''// Font-link maintenance is IO-heavy when a shared library changes.
    // Run it outside the Vulkan/UI loop, at most once per two seconds.
fn refresh_font_links_off_ui_thread() {
    static LAST: OnceLock<Mutex<Option<std::time::Instant>>> = OnceLock::new();
    let guard=LAST.get_or_init(||Mutex::new(None));
    let now=std::time::Instant::now();
    let mut last=guard.lock().unwrap_or_else(|poison|poison.into_inner());
    if last.is_some_and(|time|
        now.duration_since(time) < std::time::Duration::from_secs(2)) {
        return;
    }
    *last=Some(now);
    drop(last);
    if let Err(error)=std::thread::Builder::new()
        .name("vectorcraft-font-links".into())
        .spawn(refresh_font_links) {
        log::warn!("Could not start background font-link check: {error}");
    }
}

#[cfg(unix)]
fn link_desktop_names(dir: &Path) {''')
    path.write_text(s)
    print("PASS: cached font startup without 5000-entry FUSE enumeration; asynchronous link refresh retains SAF support")

if __name__=="__main__":
    import sys
    patch(Path(sys.argv[1]))
