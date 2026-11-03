"""Cache VectorCraft's Android system-font *symlink creation* across warm launches.

Reference builder system_fonts::install_font_env currently tears down and
recreates every system-font link synchronously before eframe can draw.
Honor devices can have many font entries; cache only these symlinks. Keep the
system font fallback, the app's private imported fonts, and the existing
2-second refresh when a user's font directory changes.
"""
import argparse
from pathlib import Path

OLD = """        let root = home.join(".fonts");
        let state = user_font_state();
        let linked = link_fonts(&root);
        for alias in [home.join(".local/share/fonts"), base.join("fonts")] {
            link_folder_alias(&alias, &root);
        }
        // Linked again when the user's own font folder changes or becomes readable (see
        // [`refresh_font_links`]), so the folder to link into is remembered here.
        let _ = FONT_LINKS.set(vec![root]);
        report_user_fonts(linked, &state);
        remember_font_state(state);"""

NEW = """        let root = home.join(".fonts");
        let state = user_font_state();
        // Cache only the symlink directory. The original implementation deleted
        // and recreated every Android system-font link on each app launch,
        // while the native window stayed completely dark. Root directory
        // metadata detects added/removed font files; the periodic refresh
        // still catches the user's folder changes later.
        let mut key = String::from("vectorcraft-font-links-v1");
        for folder in FONT_DIRS.iter().chain(USER_FONT_DIRS.iter()) {
            let path = Path::new(folder);
            let stamp = std::fs::metadata(path).ok();
            let modified = stamp.as_ref()
                .and_then(|m| m.modified().ok())
                .and_then(|m| m.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|v| v.as_nanos()).unwrap_or(0);
            let len = stamp.as_ref().map(|m| m.len()).unwrap_or(0);
            key.push_str(&format!("|{folder}:{modified}:{len}"));
        }
        let marker = home.join(".vectorcraft-font-links-cache-v1");
        let cache_hit = std::fs::read_to_string(&marker).ok().as_deref() == Some(&key)
            && root.is_dir()
            && std::fs::read_dir(&root).ok().and_then(|mut entries| entries.next()).is_some();
        if !cache_hit {
            let linked = link_fonts(&root);
            report_user_fonts(linked, &state);
            if std::fs::read_dir(&root).ok().and_then(|mut entries| entries.next()).is_some() {
                let _ = std::fs::write(&marker, &key);
            }
            log::info!("VectorCraft startup: system font links refreshed");
        } else {
            log::info!("VectorCraft startup: cached system font links reused");
        }
        for alias in [home.join(".local/share/fonts"), base.join("fonts")] {
            link_folder_alias(&alias, &root);
        }
        // Linked again when the user's own font folder changes or becomes
        // readable (see refresh_font_links). The app's imported SAF fonts are
        // cached under app-private Fonts/ and are never deleted by this code.
        let _ = FONT_LINKS.set(vec![root]);
        remember_font_state(state);"""


def apply(source: str) -> str:
    if source.count(OLD) != 1:
        raise ValueError("Pinned system_fonts.rs install_font_env section changed")
    if "vectorcraft-font-links-cache-v1" in source:
        raise ValueError("Font link caching already injected")
    return source.replace(OLD, NEW, 1)


def patch(builder: Path) -> None:
    file = builder / "templates/android/system_fonts.rs"
    file.write_text(apply(file.read_text()))
    print("PASS: cached Android font symlinks; fallback fonts and live refresh preserved")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("builder", type=Path)
    patch(p.parse_args().builder)
