//! Install bundled, pinned OCR models to app-private storage before engine startup.
use std::{fs, io::{self, Read}, path::Path, sync::OnceLock};
use sha2::{Digest, Sha256};
include!("pdfcraft_ocr_manifest.rs");
static STATUS: OnceLock<String> = OnceLock::new();
pub fn status() -> &'static str { STATUS.get().map(String::as_str).unwrap_or("OCR models not initialized") }
fn hash(path: &Path) -> io::Result<String> {
    let mut file = fs::File::open(path)?;
    let mut sha = Sha256::new();
    let mut buf = [0u8; 65536];
    loop { let n = file.read(&mut buf)?; if n == 0 { break; } sha.update(&buf[..n]); }
    Ok(format!("{:x}", sha.finalize()))
}
fn install(app: &android_activity::AndroidApp) -> io::Result<()> {
    let base = app.internal_data_path().ok_or_else(|| io::Error::other("private storage unavailable"))?.join("pdfcraft-ocr-models-v1");
    fs::create_dir_all(&base)?;
    for &(name, expected) in MODELS {
        let dest = base.join(name);
        if hash(&dest).ok().as_deref() == Some(expected) { continue; }
        let asset_name = std::ffi::CString::new(format!("models/{name}")).map_err(io::Error::other)?;
        let manager = app.asset_manager();
        let mut asset = manager.open(&asset_name).ok_or_else(|| io::Error::other(format!("missing bundled OCR asset {name}")))?;
        let temp = dest.with_extension("part");
        let result = (|| -> io::Result<()> {
            let mut file = fs::File::create(&temp)?;
            io::copy(&mut asset, &mut file)?;
            file.sync_all()?;
            drop(file);
            if hash(&temp)? != expected { return Err(io::Error::other("OCR model integrity check failed")); }
            fs::rename(&temp, &dest)?;
            Ok(())
        })();
        if result.is_err() { let _ = fs::remove_file(&temp); }
        result?;
    }
    // Called before the engine or application workers start; no runtime downloads.
    unsafe { std::env::set_var("PDFCRAFT_MODELS", &base); }
    Ok(())
}
pub fn initialize(app: &android_activity::AndroidApp) {
    let message = match install(app) {
        Ok(()) => "OCR models ready — offline English text recognition".to_string(),
        Err(err) => format!("OCR models unavailable: {err}"),
    };
    log::info!("{message}");
    let _ = STATUS.set(message);
}
