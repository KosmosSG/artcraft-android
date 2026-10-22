#!/usr/bin/env python3
"""Apply isolated, pinned DeckCraft Android font-import UI patch.

Only edits the disposable upstream checkout used by candidate CI. This does not
alter other ArtCraft apps or claim persistent/shared-folder font support.
"""
from pathlib import Path
import sys

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"DeckCraft source changed ({label}: {count} anchors); review before porting")
    return text.replace(old, new, 1)

def main(root: Path) -> None:
    ui = root / "crates/ui-egui/src/lib.rs"
    menus = root / "crates/ui-egui/src/menus.rs"
    src = ui.read_text()
    src = replace_once(src, "enum FilePurpose {\n    Open,\n", "enum FilePurpose {\n    Open,\n    Font,\n", "font purpose enum")
    src = replace_once(src, '        "open" => FilePurpose::Open,\n',
                       '        "open" => FilePurpose::Open,\n        "font" => FilePurpose::Font,\n', "purpose dispatch")
    src = replace_once(src, "        FilePurpose::Open => open_command(name),\n",
                       "        FilePurpose::Open => open_command(name),\n        FilePurpose::Font => None, // Handled before slide/media commands.\n", "command dispatch")
    src = replace_once(src, '    ("app.openDialog", "Open…", None, "{purpose?}"),\n',
                       '    ("app.openDialog", "Open…", None, "{purpose?}"),\n    ("app.importFont", "Import Font (TTF/OTF)…", None, "{}"),\n', "command palette")
    src = replace_once(src, '            "app.openDialog" => self.pick_and_open(),\n',
                       '            "app.openDialog" => self.pick_and_open(),\n            "app.importFont" => self.import_font_dialog(),\n', "UI command")
    anchor = '    pub fn open_or_insert_bytes(&mut self, name: &str, bytes: &[u8]) {\n'
    addition = r'''    /// Import an individual TTF/OTF/TTC using the existing host SAF picker.
    /// This first candidate registers faces for the running session only.
    pub fn import_font_dialog(&mut self) {
        if self.services.open_async.is_some() {
            let id = self.begin_external_file("font");
            if let Some(open) = self.services.open_async.as_mut() {
                open("font", id);
            }
        } else if let Some(pick) = self.services.pick_open.as_mut() {
            if let Some(path) = pick("font") {
                let bytes = if let Some(read) = self.services.read.as_ref() {
                    read(&path)
                } else {
                    std::fs::read(&path).map_err(|error| error.to_string())
                };
                match bytes {
                    Ok(bytes) => {
                        let name = std::path::Path::new(&path)
                            .file_name().map(|name| name.to_string_lossy().into_owned())
                            .unwrap_or_else(|| "imported-font".into());
                        self.import_font_bytes(&name, &bytes);
                    }
                    Err(error) => self.set_status(format!("Could not import font: {error}")),
                }
            }
        } else {
            self.set_status("This host has no font file picker");
        }
    }

    fn import_font_bytes(&mut self, name: &str, bytes: &[u8]) {
        let lower = name.to_ascii_lowercase();
        if ![".ttf", ".otf", ".ttc"].iter().any(|ext| lower.ends_with(ext)) {
            self.set_status(format!("{name}: select a TTF, OTF or TTC font"));
            return;
        }
        if bytes.len() < 12 || bytes.len() > 20 * 1024 * 1024 {
            self.set_status(format!("{name}: font must be between 12 bytes and 20 MiB"));
            return;
        }
        let header = &bytes[..4];
        if !(header == b"OTTO" || header == b"ttcf" || header == b"true" || header == &[0, 1, 0, 0]) {
            self.set_status(format!("{name}: invalid font header"));
            return;
        }
        let added = deckcraft_fonts::FontDb::global().add_font(bytes.to_vec());
        if added == 0 {
            self.set_status(format!("{name}: no new usable font faces (invalid or already loaded)"));
        } else {
            self.set_status(format!("Imported {added} face(s) from {name} for this session"));
        }
    }

'''
    src = replace_once(src, anchor, addition + anchor, "import method")
    src = replace_once(src,
                       '        let req = self.pending_files.remove(pos);\n        let cmd = match command_for(req.purpose, name, bytes) {\n',
                       '        let req = self.pending_files.remove(pos);\n        if req.purpose == FilePurpose::Font {\n            self.import_font_bytes(name, bytes);\n            return;\n        }\n        let cmd = match command_for(req.purpose, name, bytes) {\n',
                       "SAF inbox import")
    menu = menus.read_text()
    menu = replace_once(menu,
                        '("About DeckCraft", "app.about"), ("Command Palette", "app.palette")',
                        '("About DeckCraft", "app.about"), ("Import Font…", "app.importFont"), ("Command Palette", "app.palette")',
                        "Help catalogue")
    ui.write_text(src)
    menus.write_text(menu)
    print("DeckCraft-only session font import patched: native picker, validation, FontDb registration, command palette")
    print("Persistent font folders, shared SAF tree and updater are NOT implemented by this patch")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_deckcraft_fonts.py <pinned DeckCraft source root>")
    main(Path(sys.argv[1]))
