#!/usr/bin/env python3
"""Stage a bounded 4 GiB Android shared-font scan into the pinned PhotoCraft v0.14.0 CI workspace.

Apply ONLY after the immutable, tested baseline and the PR93 AI overlay have been
prepared in an ephemeral runner. No existing signed APK, main branch, keystore,
user documents or public release is changed. 4 GiB is a cumulative *disk scan*
budget, NOT a request to load 4 GiB into process memory.
"""
from __future__ import annotations

from pathlib import Path
import sys

FONT_LIMIT_BYTES = 4 * 1024**3
FONT_FILE_LIMIT = 5000
PER_FONT_BYTES = 32 * 1024**2

def exactly(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise ValueError(f"Expected exactly one font-source anchor; got {n}: {old[:100]!r}")
    return text.replace(old, new, 1)

def patch_java(text: str) -> str:
    text = exactly(text,
        '    private static final int REQ_FONT_FOLDER = 0x5045;',
        '    private static final int REQ_FONT_FOLDER = 0x5045;\n'
        '    // Entire SAF tree; counts disk bytes scanned, not Android RAM.\n'
        '    private static final long FONT_SCAN_MAX_BYTES = 4L * 1024 * 1024 * 1024;\n'
        '    private static final long FONT_SCAN_MAX_FILE_BYTES = 32L * 1024 * 1024;\n'
        '    private static final int FONT_SCAN_MAX_FILES = 5000;')
    text = exactly(text,
        '                int count = 0;\n                int visitedFolders = 0;',
        '                int count = 0;\n                long scannedBytes = 0L;\n'
        '                boolean scanLimitReached = false;\n                int visitedFolders = 0;')
    text = exactly(text,
        'while (!pending.isEmpty() && count < 200 && visitedFolders < 1000)',
        'while (!pending.isEmpty() && count < FONT_SCAN_MAX_FILES && visitedFolders < 1000)')
    text = exactly(text,
        'while (cursor.moveToNext() && count < 200)',
        'while (cursor.moveToNext() && count < FONT_SCAN_MAX_FILES)')
    text = exactly(text,
        '                                if (size <= 0 || size > 32L * 1024 * 1024) continue;',
        '                                if (size <= 0 || size > FONT_SCAN_MAX_FILE_BYTES) continue;\n'
        '                                if (size > FONT_SCAN_MAX_BYTES - scannedBytes) {\n'
        '                                    scanLimitReached = true;\n'
        '                                    continue;\n'
        '                                }')
    text = exactly(text,
        '                                    if (total > 32L * 1024 * 1024)\n'
        '                                        throw new Exception("Font too large: " + name);',
        '                                    if (total > FONT_SCAN_MAX_FILE_BYTES)\n'
        '                                        throw new Exception("Font too large: " + name);\n'
        '                                    if (total > FONT_SCAN_MAX_BYTES - scannedBytes) {\n'
        '                                        scanLimitReached = true;\n'
        '                                        throw new Exception("4 GiB shared font scan budget reached");\n'
        '                                    }')
    text = exactly(text,
        '                            paths.put(target.getAbsolutePath());\n                            count++;',
        '                            paths.put(target.getAbsolutePath());\n'
        '                            count++;\n'
        '                            scannedBytes += total;')
    text = exactly(text,
        '                result.put("count", count);\n'
        '                results.offer(result.toString());',
        '                result.put("count", count);\n'
        '                result.put("scanned_bytes", scannedBytes);\n'
        '                result.put("scan_budget_bytes", FONT_SCAN_MAX_BYTES);\n'
        '                result.put("scan_limit_reached", scanLimitReached\n'
        '                        || count >= FONT_SCAN_MAX_FILES || !pending.isEmpty());\n'
        '                results.offer(result.toString());')
    return text

SHARED_RUST = """    fn process_shared_font_result(&self, value: &serde_json::Value) {
        // The Java side streams at most 4 GiB *in aggregate* to app-private disk.
        // Do not read this set into RAM: ask fontique to register disk paths and
        // mmap/load a font only when the user actually selects or renders it.
        let result = (|| -> Result<String, String> {
            match value.get("status").and_then(|v| v.as_str()) {
                Some("cancel") => return Ok("Shared folder selection cancelled".into()),
                Some("ok") => {},
                _ => return Err(value.get("message").and_then(|v| v.as_str())
                    .unwrap_or("Could not read shared font folder").into()),
            }
            if value.get("kind").and_then(|v| v.as_str()) != Some("font_folder") {
                return Err("Unexpected shared folder response".into());
            }
            let paths = value.get("paths").and_then(|v| v.as_array())
                .ok_or("Shared folder returned no font list")?;
            let mut candidates = Vec::new();
            let mut skipped = 0usize;
            // Bound JSON/path count even if a provider (or malformed JNI response)
            // returns more entries than the 5,000-file Java scan limit.
            for item in paths.iter().take(5000) {
                let Some(path) = item.as_str() else { skipped += 1; continue };
                let candidate = PathBuf::from(path);
                let valid_ext = candidate.extension().and_then(|x| x.to_str())
                    .is_some_and(|x| x.eq_ignore_ascii_case("ttf") || x.eq_ignore_ascii_case("otf"));
                let valid_meta = fs::metadata(&candidate).is_ok_and(
                    |m| m.is_file() && m.len() > 0 && m.len() <= 32 * 1024 * 1024);
                if valid_ext && valid_meta { candidates.push(candidate); }
                else { skipped += 1; }
            }
            skipped += paths.len().saturating_sub(5000);
            let mut engine = photocraft_text::shared()
                .lock().map_err(|e| format!("Font engine lock failed: {e}"))?;
            let indexed = engine.fonts.register_font_paths(&candidates);
            skipped += candidates.len().saturating_sub(indexed);
            let bytes = value.get("scanned_bytes").and_then(|v| v.as_u64())
                .unwrap_or(0).min(4 * 1024 * 1024 * 1024);
            let suffix = if value.get("scan_limit_reached").and_then(|v| v.as_bool()) == Some(true) {
                "; scan limit reached (more font files may remain)"
            } else { "" };
            Ok(format!("Shared font files indexed: {indexed}; skipped: {skipped}; scanned: {:.1} MiB / 4096 MiB{suffix}",
                bytes as f64 / (1024.0 * 1024.0)))
        })();
        *self.shared_font_status.lock().unwrap_or_else(|e| e.into_inner()) =
            result.unwrap_or_else(|error| format!("Shared fonts: {error}"));
    }

"""

def patch_rust_adapter(text: str) -> str:
    start = '    fn process_shared_font_result(&self, value: &serde_json::Value) {'
    end = '    fn process_font_result(&self, bridge: &AndroidFileBridge, id: u64, value: &serde_json::Value) {'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("PhotoCraft shared-folder handler changed")
    a, b = text.index(start), text.index(end)
    if b <= a:
        raise ValueError("Invalid PhotoCraft shared-folder handler order")
    old = text[a:b]
    if "fs::read(path)" not in old or "register_custom_font" not in old:
        raise ValueError("Expected RAM-eager shared-folder handler before migration")
    return text[:a] + SHARED_RUST + text[b:]

UPSTREAM_RUST = """    /// Register SAF-cached shared-font files by PATH, not by allocating all
    /// their bytes. Fontique's file source loads/memory-maps faces when needed,
    /// letting a library totaling 4 GiB be catalogued on a memory-limited phone.
    /// Individual font import is still intentionally limited to 32 MiB.
    pub fn register_font_paths(&mut self, paths: &[std::path::PathBuf]) -> usize {
        use std::io::Read as _;
        let mut accepted = Vec::new();
        let mut total_bytes = 0u64;
        for path in paths {
            let Ok(meta) = std::fs::metadata(path) else { continue };
            if !meta.is_file() || meta.len() == 0 || meta.len() > 32 * 1024 * 1024 {
                continue;
            }
            // Java enforces this budget, but fail closed on malformed JNI data too.
            if meta.len() > 4u64 * 1024 * 1024 * 1024 - total_bytes {
                continue;
            }
            let Ok(mut source) = std::fs::File::open(path) else { continue };
            let mut header = [0u8; 4];
            if source.read_exact(&mut header).is_err() {
                continue;
            }
            if !matches!(header,
                [0, 1, 0, 0] | [b'O', b'T', b'T', b'O'] |
                [b't', b'r', b'u', b'e'] | [b't', b't', b'c', b'f']) {
                continue;
            }
            accepted.push(path.as_path());
            total_bytes += meta.len();
        }
        if accepted.is_empty() {
            return 0;
        }
        self.fcx.collection.load_fonts_from_paths(accepted.iter().copied());
        self.ps_cache.clear();
        self.face_cache.clear();
        self.refresh_generics();
        GENERATION.fetch_add(1, Ordering::Relaxed);
        if self.shared {
            SHARED_GENERATION.fetch_add(1, Ordering::Relaxed);
        }
        accepted.len()
    }

"""

def patch_upstream_fonts(text: str) -> str:
    anchor = '    /// Registers font data (TTF/OTF, or every face of a TTC/OTC). Returns the family names added.'
    if "fn register_font_paths(" in text:
        raise ValueError("Upstream already has path registration; review interface")
    return exactly(text, anchor, UPSTREAM_RUST + anchor)

def stage(root: Path) -> None:
    java = root / "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java"
    adapter = root / "adapters/photocraft/src/lib.rs"
    upstream = root / "source/photocraft/crates/text/src/fonts.rs"
    # Validate ALL three pinned sources before modifying any of them. A changed
    # upstream anchor must not leave a half-patched, buildable runner workspace.
    changes = []
    for file, patch in ((java, patch_java), (adapter, patch_rust_adapter),
                        (upstream, patch_upstream_fonts)):
        if not file.is_file():
            raise ValueError("Missing pinned font source: " + str(file))
        raw = file.read_text()
        modified = patch(raw)
        if raw == modified:
            raise ValueError("Font scanner patch made no change: " + str(file))
        changes.append((file, modified))
    for file, modified in changes:
        file.write_text(modified)
        print("STAGED (ephemeral runner only):", file)
    print("PASS: 4 GiB aggregate SAF scan / 5,000 files / 32 MiB per font")
    print("PASS: shared font engine uses paths (lazy file-backed loading), not fs::read on entire catalog")
    print("NO PRIVATE KEY / NO APK SIGNED / NO PUBLIC RELEASE")

def self_test() -> None:
    assert FONT_LIMIT_BYTES == 4294967296
    assert FONT_FILE_LIMIT == 5000
    assert PER_FONT_BYTES == 33554432
    for bad in ((0, "x", "y"), (2, "x", "y")):
        try:
            exactly("x" * bad[0], bad[1], bad[2])
        except ValueError:
            pass
        else:
            raise AssertionError("source guard did not fail closed")
    assert "load_fonts_from_paths" in UPSTREAM_RUST
    assert "4u64 * 1024 * 1024 * 1024 - total_bytes" in UPSTREAM_RUST
    assert "total_bytes += meta.len();" in UPSTREAM_RUST
    assert "std::fs::read" not in UPSTREAM_RUST
    assert "fs::read(path)" not in SHARED_RUST
    assert "register_font_paths(&candidates)" in SHARED_RUST
    assert "scan_limit_reached" in SHARED_RUST
    print("PASS: 4 GiB capacity, fail-closed patching and lazy registration invariants")

if __name__ == "__main__":
    try:
        if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
            self_test()
        elif len(sys.argv) == 2:
            stage(Path(sys.argv[1]).resolve())
        else:
            raise ValueError("usage: photocraft_ai_fontscan_4g_stage.py --self-test|ROOT")
    except (OSError, ValueError) as error:
        raise SystemExit("STOP: safe 4 GiB font scanner patch refused: " + str(error))
