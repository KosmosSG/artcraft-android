//! EffectCraft-specific persistent font import implementation component.
//!
//! This file is staged on the isolated EffectCraft draft branch and **is not yet
//! wired** to its Android Activity, SAF picker, or launcher UI. The future shell
//! must call `import_font` with a registrar backed by
//! `effectcraft_text::fonts::add_font_data(bytes.to_vec())` and call
//! `restore_fonts` for private `custom-fonts/` and SAF-staged shared cache.
//! No PhotoCraft crate or another app's signing material is used.

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

pub const MAX_FONT_BYTES: usize = 32 * 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ImportReport {
    pub stored_path: PathBuf,
    pub registered_faces: usize,
}

/// TTF and OTF only. The name is untrusted input from Android's document picker.
fn font_extension(file_name: &Path) -> Result<&'static str, String> {
    match file_name.extension().and_then(|value| value.to_str())
        .unwrap_or_default().to_ascii_lowercase().as_str()
    {
        "ttf" => Ok("ttf"),
        "otf" => Ok("otf"),
        _ => Err("Choose a .ttf or .otf font".into()),
    }
}

fn validate_sfnt_bytes(bytes: &[u8]) -> Result<(), String> {
    if bytes.is_empty() || bytes.len() > MAX_FONT_BYTES {
        return Err("Font must be between 1 byte and 32 MiB".into());
    }
    if bytes.len() < 12 {
        return Err("Font is too short to contain a valid SFNT header".into());
    }
    let tag = &bytes[..4];
    if tag == [0, 1, 0, 0] || tag == b"OTTO" || tag == b"true" || tag == b"typ1" {
        Ok(())
    } else {
        Err("Not a supported TrueType or OpenType SFNT font".into())
    }
}

/// Read a SAF-staged/private font without loading an unbounded file into memory.
pub fn read_font(source: &Path) -> Result<Vec<u8>, String> {
    let _ = font_extension(source)?;
    let file = File::open(source).map_err(|e| format!("Open font: {e}"))?;
    if file.metadata().map_err(|e| e.to_string())?.len() > MAX_FONT_BYTES as u64 {
        return Err("Font exceeds the 32 MiB limit".into());
    }
    let mut bytes = Vec::new();
    file.take(MAX_FONT_BYTES as u64 + 1).read_to_end(&mut bytes)
        .map_err(|e| format!("Read font: {e}"))?;
    validate_sfnt_bytes(&bytes)?;
    Ok(bytes)
}

fn safe_stem(source: &Path) -> String {
    let stem = source.file_stem().and_then(|v| v.to_str()).unwrap_or("font");
    let name: String = stem.chars().take(72).map(|c| {
        if c.is_ascii_alphanumeric() || c == '-' || c == '_' { c } else { '_' }
    }).collect();
    if name.is_empty() { "font".into() } else { name }
}

/// Persist one imported font without overwriting any existing private font.
/// The registrar is a closure so this module can be tested without the
/// EffectCraft workspace; in-app it must invoke effectcraft_text::fonts.
pub fn import_font<F>(
    source: &Path, private_dir: &Path, register: F
) -> Result<ImportReport, String>
where
    F: FnOnce(&[u8]) -> usize,
{
    let bytes = read_font(source)?;
    fs::create_dir_all(private_dir).map_err(|e| format!("Create font library: {e}"))?;
    let stem = safe_stem(source);
    let ext = font_extension(source)?;
    for i in 0..1000 {
        let name = if i == 0 { format!("{stem}.{ext}") }
                   else { format!("{stem}-{i}.{ext}") };
        let target = private_dir.join(name);
        let mut file = match OpenOptions::new().write(true).create_new(true).open(&target) {
            Ok(file) => file,
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(format!("Store font: {e}")),
        };
        if let Err(e) = file.write_all(&bytes).and_then(|()| file.sync_all()) {
            drop(file);
            let _ = fs::remove_file(&target);
            return Err(format!("Store font: {e}"));
        }
        drop(file);
        let count = register(&bytes);
        if count == 0 {
            let _ = fs::remove_file(&target);
            return Err("Font engine found no supported faces; import not stored".into());
        }
        return Ok(ImportReport { stored_path: target, registered_faces: count });
    }
    Err("Too many files with the same font name".into())
}

/// Restore private fonts at startup or reload a SAF-staged shared cache.
/// The SAF grant and recursive bounded enumeration belong to the Java bridge;
/// only app-private staged paths reach this routine.
pub fn restore_fonts<F>(private_dir: &Path, mut register: F) -> Vec<(PathBuf, Result<usize, String>)>
where
    F: FnMut(&[u8]) -> usize,
{
    let Ok(entries) = fs::read_dir(private_dir) else { return Vec::new() };
    let mut items: Vec<PathBuf> = entries.flatten().map(|e| e.path())
        .filter(|p| p.is_file() && font_extension(p).is_ok()).collect();
    items.sort();
    items.into_iter().map(|p| {
        let status = read_font(&p).and_then(|bytes| {
            match register(&bytes) {
                0 => Err("No supported font faces".into()),
                n => Ok(n),
            }
        });
        (p, status)
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn fixture_dir() -> PathBuf {
        let n = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("effectcraft-font-import-{}-{n}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn fake_ttf() -> Vec<u8> {
        let mut b = vec![0; 32]; b[0..4].copy_from_slice(&[0,1,0,0]); b
    }

    #[test]
    fn validates_extension_and_header() {
        let base = fixture_dir();
        let invalid = base.join("font.ttf");
        fs::write(&invalid, b"not a font").unwrap();
        assert!(read_font(&invalid).is_err());
        let wrong = base.join("font.txt");
        fs::write(&wrong, fake_ttf()).unwrap();
        assert!(read_font(&wrong).is_err());
        fs::write(&invalid, fake_ttf()).unwrap();
        assert_eq!(read_font(&invalid).unwrap().len(), 32);
        fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn import_is_durable_and_never_overwrites() {
        let base = fixture_dir();
        let source = base.join("Some Fancy.ttf");
        let dir = base.join("custom-fonts");
        fs::write(&source, fake_ttf()).unwrap();
        let a = import_font(&source, &dir, |_| 1).unwrap();
        let b = import_font(&source, &dir, |_| 1).unwrap();
        assert_ne!(a.stored_path, b.stored_path);
        assert_eq!(restore_fonts(&dir, |_| 1).len(), 2);
        fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn invalid_faces_do_not_remain_on_disk() {
        let base = fixture_dir();
        let source = base.join("font.otf");
        let dir = base.join("private");
        let mut data = fake_ttf();
        data[0..4].copy_from_slice(b"OTTO");
        fs::write(&source, data).unwrap();
        assert!(import_font(&source, &dir, |_| 0).is_err());
        assert!(restore_fonts(&dir, |_| 1).is_empty());
        fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn never_trusts_oversized_files() {
        let base = fixture_dir();
        let source = base.join("huge.otf");
        let file = File::create(&source).unwrap();
        file.set_len(MAX_FONT_BYTES as u64 + 1).unwrap();
        assert!(read_font(&source).is_err());
        fs::remove_dir_all(base).unwrap();
    }
}
