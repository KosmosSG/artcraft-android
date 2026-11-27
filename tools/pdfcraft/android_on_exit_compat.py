#!/usr/bin/env python3
"""Align PDFCraft Android's eframe::App::on_exit with pinned upstream eframe 0.37."""
from pathlib import Path
import sys

src = Path(sys.argv[1])
app = src / "apps/pdfcraft-android/src/lib.rs"
text = app.read_text()
old = "    fn on_exit(&mut self) {"
new = "    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {"
if new in text:
    print("PASS: PDFCraft Android on_exit already matches eframe 0.37")
elif text.count(old) == 1:
    app.write_text(text.replace(old, new, 1))
    print("PASS: updated PDFCraft Android on_exit for eframe 0.37")
else:
    raise SystemExit(
        "PDFCraft Android on_exit signature changed; expected exactly one legacy "
        "one-argument implementation, refusing an unreviewed patch"
    )
