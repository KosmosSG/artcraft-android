#!/usr/bin/env python3
"""Exercise the actual builder's guarded patches and generator against a source checkout."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

root = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]).resolve()
script = (root / 'lib/build-common.sh').read_text()
blocks = re.findall(r"<<'PY'\n(.*?)\nPY", script, re.S)
patch = next(b for b in blocks if 'src, app, title =' in b)
generator = next(b for b in blocks if 'root, src_s, app, title,' in b)
for block in blocks:
    compile(block, '<builder>', 'exec')
with tempfile.TemporaryDirectory() as folder:
    dst = Path(folder) / 'source'
    shutil.copytree(source, dst, ignore=shutil.ignore_patterns('.git', 'target'))
    def run(code, *args):
        subprocess.run([sys.executable, '-c', code, *map(str, args)], check=True,
                       env={**os.environ, 'PDFCRAFT_ANDROID_VERSION_NAME': '0.12.1-android.2'})
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    scanner = (dst / 'crates/engine/src/text_fonts.rs').read_text()
    assert ']);\n        }\n        if let Some(folder) = std::env::var_os("PDFCRAFT_ANDROID_FONT_DIR")' in scanner
    before = scanner
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    assert (dst / 'crates/engine/src/text_fonts.rs').read_text() == before
    run(generator, root, dst, 'pdfcraft', 'PDFCraft', '35', 'PDFCraft', '', '')
    android = dst / 'apps/pdfcraft-android'
    cargo = tomllib.loads((android / 'Cargo.toml').read_text())
    assert cargo['package']['version'] == '0.12.1-android.2'
    assert cargo['package']['metadata']['android']['package'] == 'com.artcraft.pdfcraft'
    native = (android / 'src/lib.rs').read_text()
    assert 'modifiers: AndroidModifiers' in native
    assert 'shell.pdf_mobile.set_renderer(description)' in native
    assert 'self.pdf_mobile.toolbar(ui)' not in native
    assert 'self.pdf_mobile.dialog(ui.ctx())' in native
    assert 'take_android_tools_request()' in native
    chrome = (dst / 'crates/ui-egui/src/chrome.rs').read_text()
    assert chrome.count('static ANDROID_TOOLS_REQUEST:') == 1
    assert 'Import Fonts…' in chrome
    mobile = (root / 'templates/android/pdfcraft_mobile.rs').read_text()
    assert 'Panel::bottom' not in mobile
    assert 'Show Android tools' not in mobile
    assert 'take_android_update_request()' in native
    assert 'self.pdf_mobile.do_update_check()' in native
    assert 'ANDROID_UPDATE_REQUEST' in (dst / 'crates/ui-egui/src/updates.rs').read_text()
print('PASS: embedded Python syntax, guarded patches, idempotence, Android generator, identity/version and Help bridge')
