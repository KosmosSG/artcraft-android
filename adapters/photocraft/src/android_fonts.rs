//! Background Android SAF font cataloguing.
//! Scan caps: <= 5,000 files and <= 4 GiB cumulative on disk.
//! IMPORTANT: never parse thousands of font faces or acquire the shared font
//! catalog mutex in the egui UI/render thread (previous Refresh Fonts freeze).
use crate::AndroidFileBridge;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, Sender};

const MAX_FILES: usize = 5_000;
const MAX_BYTES: u64 = 4 * 1024 * 1024 * 1024;
const MAX_ONE_FONT: u64 = 32 * 1024 * 1024;
const BATCH: usize = 8;

enum Job {
    Restore(PathBuf),
    Add(Vec<PathBuf>),
}
enum ResultMessage {
    Finished { indexed: usize, scanned: usize, truncated: bool },
    Failed(String),
}

pub(crate) struct AndroidFonts {
    message: Option<String>,
    visible: bool,
    tx: Sender<Job>,
    rx: Receiver<ResultMessage>,
}

fn supported(path: &Path) -> bool {
    path.extension().and_then(|x| x.to_str()).is_some_and(|ext| {
        ext.eq_ignore_ascii_case("ttf") || ext.eq_ignore_ascii_case("otf")
            || ext.eq_ignore_ascii_case("ttc") || ext.eq_ignore_ascii_case("otc")
    })
}

fn bounded_recursive_scan(folder: &Path) -> (Vec<PathBuf>, bool) {
    let mut pending = vec![folder.to_path_buf()];
    let mut paths = Vec::new();
    let mut bytes = 0u64;
    let mut visited_folders = 0usize;
    let mut truncated = false;
    while let Some(dir) = pending.pop() {
        visited_folders += 1;
        if visited_folders > 1_000 { truncated = true; break; }
        let Ok(iter) = std::fs::read_dir(&dir) else { continue };
        for entry in iter.flatten() {
            let Ok(kind) = entry.file_type() else { continue };
            if kind.is_symlink() { continue; }
            let path = entry.path();
            if kind.is_dir() {
                pending.push(path);
                continue;
            }
            if !kind.is_file() || !supported(&path) { continue; }
            let Ok(meta) = entry.metadata() else { continue };
            let size = meta.len();
            if size == 0 || size > MAX_ONE_FONT { continue; }
            if paths.len() >= MAX_FILES || size > MAX_BYTES.saturating_sub(bytes) {
                truncated = true;
                break;
            }
            bytes += size;
            paths.push(path);
        }
        if truncated { break; }
    }
    (paths, truncated || !pending.is_empty())
}
fn background(rx: Receiver<Job>, tx: Sender<ResultMessage>) {
    // Limit locking time and process large imported directories off the UI
    // thread. Faces are loaded lazily by PhotoCraft's existing catalog.
    while let Ok(job) = rx.recv() {
        let (paths, truncated) = match job {
            Job::Restore(folder) => bounded_recursive_scan(&folder),
            Job::Add(paths) => {
                let mut chosen = Vec::new();
                let mut bytes = 0u64;
                let mut truncated = false;
                for path in paths {
                    if !supported(&path) { continue; }
                    let Ok(meta) = std::fs::metadata(&path) else { continue };
                    let size = meta.len();
                    if size == 0 || size > MAX_ONE_FONT { continue; }
                    if chosen.len() == MAX_FILES || size > MAX_BYTES.saturating_sub(bytes) {
                        truncated = true;
                        break;
                    }
                    chosen.push(path);
                    bytes += size;
                }
                (chosen, truncated)
            }
        };
        let mut indexed = 0usize;
        let mut failed = false;
        for batch in paths.chunks(BATCH) {
            match photocraft_text::shared().lock() {
                Ok(mut shared) => { indexed += shared.fonts.register_font_paths(batch); }
                Err(_) => {
                    let _ = tx.send(ResultMessage::Failed("Font catalog lock unavailable".into()));
                    failed = true;
                    break;
                }
            }
            // Yield to UI drawing and font picker requests between small batches.
            std::thread::sleep(std::time::Duration::from_millis(8));
        }
        if !failed {
            let _ = tx.send(ResultMessage::Finished {
                indexed, scanned: paths.len(), truncated,
            });
        }
    }
}

impl AndroidFonts {
    pub(crate) fn new(dir: &Path) -> Self {
        let (jobs, receiver) = mpsc::channel();
        let (results, rx) = mpsc::channel();
        std::thread::Builder::new()
            .name("photocraft-font-index".into())
            .spawn(move || background(receiver, results))
            .expect("Could not create PhotoCraft font indexing worker");
        let _ = jobs.send(Job::Restore(dir.join("PhotoCraft/fonts-imported")));
        Self { message: None, visible: false, tx: jobs, rx }
    }
    pub(crate) fn poll(&mut self, bridge: &AndroidFileBridge) {
        for _ in 0..4 {
            let result = match bridge.poll_font_import() {
                Ok(Some(s)) => s,
                Ok(None) => break,
                Err(err) => {
                    self.message = Some(format!("Font picker: {err}"));
                    self.visible = true;
                    break;
                }
            };
            let Ok(info) = serde_json::from_str::<serde_json::Value>(&result) else { continue };
            let status = info["status"].as_str().unwrap_or("error");
            if status == "cancel" { continue; }
            if status != "ok" {
                self.message = Some(format!("Import Fonts: {}",
                    info["message"].as_str().unwrap_or("Unknown Android error")));
                self.visible = true;
                continue;
            }
            let paths: Vec<PathBuf> = info["paths"].as_array().into_iter().flatten()
                .filter_map(|v| v.as_str().map(PathBuf::from))
                .take(MAX_FILES).collect();
            let count = paths.len();
            if self.tx.send(Job::Add(paths)).is_err() {
                self.message = Some("Font indexer unavailable; imported files remain on disk.".into());
            } else {
                self.message = Some(format!(
                    "Imported {count} font file(s). Indexing in background; font family list updates when ready."
                ));
            }
            self.visible = true;
        }
        while let Ok(done) = self.rx.try_recv() {
            self.message = Some(match done {
                ResultMessage::Finished { indexed, scanned, truncated } =>
                    format!("Font indexing finished: {indexed} registered / {scanned} scanned{}.",
                        if truncated { " (4 GiB / 5,000-file limit reached)" } else { "" }),
                ResultMessage::Failed(error) =>
                    format!("Could not finish font indexing: {error}"),
            });
            // Do not present a popup on the initial silent background restore.
            if self.visible {
                // Existing import dialog already open; update its progress.
            }
        }
    }
    pub(crate) fn show(&mut self, ctx: &egui::Context) {
        if !self.visible { return; }
        let mut open = self.visible;
        egui::Window::new("Import Fonts")
            .open(&mut open)
            .collapsible(false)
            .resizable(false)
            .show(ctx, |ui| {
                if let Some(s) = &self.message { ui.label(s); }
                ui.label("Imported TTF/OTF fonts are saved to the PhotoCraft font library.");
            });
        self.visible = open;
    }
}
