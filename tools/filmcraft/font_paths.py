"""Writable font directories from DesignCraft android.5, applied only to FilmCraft staging."""

def patch_android_font_paths(text: str) -> str:
    """Align the pinned DesignCraft Android font scanner with writable font imports."""
    legacy_link = '''        if !link.exists() {
            let _ = std::os::unix::fs::symlink("/system/fonts", &link);
        }
'''
    writable_link = '''        // Only replace legacy links to Android's read-only system directory;
        // leave real user directories and already-imported fonts untouched.
        if std::fs::read_link(&link).ok().as_deref()
            == Some(std::path::Path::new("/system/fonts"))
        {
            let _ = std::fs::remove_file(&link);
        }
        if std::fs::create_dir_all(&link).is_ok() {
            let system_link = link.join("android-system");
            if std::fs::symlink_metadata(&system_link).is_err() {
                let _ = std::os::unix::fs::symlink("/system/fonts", &system_link);
            }
        }
'''
    if text.count(legacy_link) != 1:
        raise ValueError("Pinned Android font directory bootstrap changed; review required")
    text = text.replace(legacy_link, writable_link)
    xdg = 'std::env::set_var("XDG_DATA_HOME", &base);'
    if text.count(xdg) != 1:
        raise ValueError("Pinned Android XDG font search path changed; review required")
    return text.replace(xdg,
        'std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));')


