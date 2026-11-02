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
                       env={**os.environ, 'PDFCRAFT_ANDROID_VERSION_NAME': '0.17.0-android.5'})
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    scanner = (dst / 'crates/engine/src/text_fonts.rs').read_text()
    assert ']);\n        }\n        if let Some(folder) = std::env::var_os("PDFCRAFT_ANDROID_FONT_DIR")' in scanner
    before = scanner
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    assert (dst / 'crates/engine/src/text_fonts.rs').read_text() == before
    run(generator, root, dst, 'pdfcraft', 'PDFCraft', '35', 'PDFCraft', '', '')
    android = dst / 'apps/pdfcraft-android'
    cargo = tomllib.loads((android / 'Cargo.toml').read_text())
    assert cargo['package']['version'] == '0.17.0-android.5'
    assert cargo['package']['metadata']['android']['package'] == 'com.artcraft.pdfcraft'
    native = (android / 'src/lib.rs').read_text()
    assert 'modifiers: AndroidModifiers' in native
    assert 'shell.pdf_mobile.set_renderer(description)' in native
    assert 'if self.inner.android_tools_visible() {' in native
    assert native.index('self.pdf_mobile.toolbar(ui)') < native.index('self.inner.ui(ui, frame)')
    assert 'inner.set_android_tools_visible(pdf_mobile.toolbar_shown());' in native
    assert 'self.pdf_mobile.sync_toolbar_preference(self.inner.android_tools_visible());' in native
    menu = (dst / 'crates/ui-egui/src/menus.rs').read_text()
    assert 'ARTCRAFT_ANDROID_TOOLS_VISIBLE' in menu
    assert 'pub fn android_tools_visible(&self) -> bool' in menu
    assert 'pub fn set_android_tools_visible(&self, visible: bool)' in menu
    assert 'view.push(self.menu_item(ANDROID_TOOLS, None))' in menu
    assert 'ANDROID_TOOLS => Some(ARTCRAFT_ANDROID_TOOLS_VISIBLE.load(' in menu
    mobile_toolbar = (root / 'templates/android/pdfcraft_mobile.rs').read_text()
    # Regression: the font picker and shared-folder controls must be visible
    # without expanding a nested panel on HONOR Android tablet screens.
    for label in ('Import Font…', 'Choose Shared Font Folder…', 'Refresh Font Folder'):
        assert 'ui.button("' + label + '")' in mobile_toolbar
    assert 'fonts_open' not in mobile_toolbar
    assert 'ui.button("Hide panel")' in mobile_toolbar
    # PDFCraft light theme sets dark text, so a transparent group drew black
    # system surface behind it. The panel MUST paint its own dynamic theme fill.
    assert 'egui::Frame::group(parent.style())' in mobile_toolbar
    assert '.fill(parent.visuals().panel_fill)' in mobile_toolbar
    assert 'ui.set_min_width((available_width - 14.0).max(0.0))' in mobile_toolbar
    assert 'parent.group(|ui|' not in mobile_toolbar
    assert 'pub fn toolbar(&mut self, parent: &mut egui::Ui) -> bool' in mobile_toolbar
    assert 'pub fn sync_toolbar_preference(&mut self, visible: bool)' in mobile_toolbar
    assert 'egui::Panel::bottom("pdfcraft_android_tools")' not in mobile_toolbar
    assert mobile_toolbar.index('ui.button("Import Font…")') < mobile_toolbar.index('ui.button("Check updates")')
    assert 'take_android_update_request()' in native
    assert 'self.pdf_mobile.do_update_check()' in native
    assert 'ANDROID_UPDATE_REQUEST' in (dst / 'crates/ui-egui/src/platform/updates.rs').read_text()
    # Updater must search beyond page 1 of the multi-app release feed.
    bridge = (root / 'templates/android/pdfcraft_mobile_java.txt').read_text()
    assert 'releases?per_page=100&page=' in bridge
    assert 'PDF_RELEASES_MAX_PAGES = 3' in bridge
    assert 'pdfToolbarVisible()' in bridge and 'pdfSetToolbarVisible(boolean visible)' in bridge
    assert 'PDF_TOOLBAR_VISIBILITY_PREF' in bridge
    assert 'PDF_FONT_SCAN_MAX_BYTES = 4L * 1024 * 1024 * 1024' in bridge
    assert 'PDF_FONT_SCAN_MAX_FILES = 5000' in bridge
    assert 'PDF_FONT_SCAN_MAX_FOLDERS = 10000' in bridge
    assert 'pdfCopyFont(font, name, scanBytes)' in bridge
    assert 'PDF_RELEASES_API + page' in bridge
    assert 'if (conn != null) conn.disconnect();' in bridge
    assert 'PDFCraft-v' in bridge and '-arm64-release.apk' in bridge
    assert 'pdfCompareVersions(latest, installed) > 0' in bridge
print('PASS: embedded Python syntax, guarded patches, idempotence, Android generator, identity/version and Help bridge')
