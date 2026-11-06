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
# Regression guard: pinned upstream v0.18.0 must receive the Android IME-reset
# winit overlay; a skipped guard compiled but failed at egui-winit previously.
assert '"\u0024{PDFCRAFT_REF:-}" == "v0.18.0"' in script, 'v0.18 IME winit overlay was skipped by builder'
assert '|| "\u0024{PDFCRAFT_REF:-}" == "v0.18.0" ) ]]; then' in script, 'v0.18 Android arboard compatibility guard missing'


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
                       env={**os.environ, 'PDFCRAFT_ANDROID_VERSION_NAME': '0.18.0-android.13'})
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    scanner = (dst / 'crates/engine/src/text_fonts.rs').read_text()
    assert ']);\n        }\n        if let Some(folder) = std::env::var_os("PDFCRAFT_ANDROID_FONT_DIR")' in scanner
    before = scanner
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    assert (dst / 'crates/engine/src/text_fonts.rs').read_text() == before
    run(generator, root, dst, 'pdfcraft', 'PDFCraft', '35', 'PDFCraft', '', '')
    android = dst / 'apps/pdfcraft-android'
    cargo = tomllib.loads((android / 'Cargo.toml').read_text())
    assert cargo['package']['version'] == '0.18.0-android.13'
    assert cargo['dependencies']['egui-winit']['path'] == '../../vendor/egui-winit'
    assert cargo['dependencies']['sha2'] == '0.10'
    assert cargo['package']['metadata']['android']['assets'] == 'ocr-assets'
    assert cargo['package']['metadata']['android']['package'] == 'com.artcraft.pdfcraft'
    native = (android / 'src/lib.rs').read_text()
    assert 'modifiers: AndroidModifiers' in native
    assert 'mod pdfcraft_ocr;' in native
    assert native.index('pdfcraft_ocr::initialize(&android_app);') < native.index('let saf_bridge = saf::Bridge::new(&android_app);')
    assert (android / 'src/pdfcraft_ocr.rs').is_file()
    assert 'android_input_patch' in (root/'tools/pdfcraft/winit_v015_compat.py').read_text()
    assert 'ctrl_shortcuts_without_separate_modifier_key_event' in (root/'templates/android/pdfcraft_modifiers.rs').read_text()
    assert 'shell.pdf_mobile.set_renderer(description)' in native
    assert 'egui_winit::pdfcraft_adaptive_cursor::set_activity(app.activity_as_ptr() as usize);' in native
    assert 'egui_winit::pdfcraft_adaptive_cursor::apply(ui.ctx().output(|o| o.cursor_icon));' in native
    assert 'PDFCRAFT_ANDROID_POST_UI_CURSOR_FALLBACK' in (root / 'lib/build-common.sh').read_text()
    assert 'self.pdf_mobile.dialog(ui.ctx())' in native
    assert 'self.pdf_mobile.observe_raw_input(raw);' in native
    assert 'self.pdf_mobile.handle_menu(self.inner.take_android_tools_request())' in native
    assert 'renderer: eframe::Renderer::Wgpu' in native
    assert 'Hardware GPU reported' in native
    assert 'Software CPU adapter reported' in native
    assert 'PDF pages: hayro CPU rasterization' in native
    mobile = (root / 'templates/android/pdfcraft_mobile.rs').read_text()
    assert 'GPU info' in mobile
    assert 'gpu_details_open' in mobile
    assert 'self.gpu_details_open = !self.gpu_details_open' in mobile
    assert 'ui.label(&self.renderer)' in mobile
    assert 'if self.inner.android_tools_visible() {' in native
    assert native.index('self.pdf_mobile.toolbar(ui)') < native.index('self.inner.ui(ui, frame)')
    assert 'inner.set_android_tools_visible(pdf_mobile.toolbar_shown());' in native
    assert 'self.pdf_mobile.sync_toolbar_preference(self.inner.android_tools_visible());' in native
    menu = (dst / 'crates/ui-egui/src/menus.rs').read_text()
    canvas = (dst / 'crates/ui-egui/src/canvas.rs').read_text()
    app = (dst / 'crates/ui-egui/src/app.rs').read_text()
    assert 'PDFCRAFT_ANDROID_SELECT_TOUCH_NOT_SCROLL' in canvas
    assert 'PDFCRAFT_ANDROID_BARE_TOOL_KEYS' in app
    keys = (dst / 'crates/ui-egui/src/app/keys.rs').read_text()
    prompt = (dst / 'crates/ui-egui/src/dialogs/prompts.rs').read_text()
    assert 'ARTCRAFT_ANDROID_DCS' in prompt
    assert 'PDFCRAFT_ANDROID_DCS_MODAL_FALLBACK' in prompt
    assert 'egui::ImeEvent::Commit(text)' in prompt
    assert 'PDFCRAFT_ANDROID_REPEAT_VH' in keys
    assert 'PDFCRAFT_ANDROID_VH_EVENT_FALLBACK' in keys
    assert 'event::WindowEvent::PanGesture' in (root/'tools/pdfcraft/android_input_patch.py').read_text()
    assert 'ARTCRAFT_ANDROID_REPEAT_TOOL_KEYS' in keys
    assert 'pdfcraft-touch-select-hint' not in canvas
    assert 'Touch: swipe to scroll' not in canvas
    assert 'PDFCRAFT_ANDROID_TOUCH_HINT_REMOVED' in (root / 'tools/pdfcraft/android_interaction_patch.py').read_text()
    # Android.8 deliberately removes the duplicate H/V command consumer.
    # Native PdfCraftApp::tool_keys remains the sole shortcut dispatcher.
    assert 'self.android_bare_tool_keys(ctx);' not in app
    assert 'ARTCRAFT_ANDROID_REPEAT_KEYS' in app
    assert 'QuickTool::Hand' in app and 'Key::H' in app and 'QuickTool::Select' in app
    assert 'ARTCRAFT_ANDROID_TOOLS_VISIBLE' in menu
    assert 'pub fn android_tools_visible(&self) -> bool' in menu
    assert 'pub fn set_android_tools_visible(&self, visible: bool)' in menu
    assert 'view.push(self.menu_item(ANDROID_TOOLS, None))' in menu
    assert 'PDFCRAFT_ANDROID_HELP_REQUEST' in menu
    assert 'PDFCRAFT_ANDROID_ICON_MENU' in menu
    assert 'crate::android_approved_brand::paint(ui.painter(), rect.shrink(2.0))' in menu
    assert '"Import Fonts…"' in menu and '"Check updates"' in menu
    assert '"Startup update check settings…"' in menu
    assert '"Trackpad diagnostics…"' in menu
    assert '"android.import_fonts"' not in menu
    assert 'PDFCRAFT_ANDROID_BIDIRECTIONAL_PINCH' in (root / 'tools/pdfcraft/android_input_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_PINCH' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_GESTURE_AXES_34' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_SCROLL_LOCK' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_PHASED_SCROLL' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'ANDROID_TOOLS => Some(ARTCRAFT_ANDROID_TOOLS_VISIBLE.load(' in menu
    # The optional View toolbar and the separately approved stable Help dialog
    # are different interfaces. The Help dialog legitimately retains fonts_open.
    assert 'pub fn handle_menu(&mut self, action: u8)' in mobile
    assert 'self.do_update_check();' in mobile and 'self.gpu_details_open = true;' in mobile
    assert 'PDFCRAFT_ANDROID_EGUI_SCROLL_DIAGNOSTICS' in mobile
    assert 'egui::Event::MouseWheel { unit, delta, .. }' in mobile
    assert 'egui::Event::Zoom(factor)' in mobile
    assert 'read_trackpad_status' in mobile
    assert '"Adaptive cursor diagnostics"' in mobile
    assert 'PDFCRAFT_ANDROID_CURSOR_OUTPUT_DIAGNOSTICS' in mobile
    assert 'i.pointer.latest_pos()' in mobile
    assert 'ui.ctx().output(|o| o.cursor_icon)' in mobile
    assert '"Android cursor requests: {}"' in mobile
    assert 'pub fn dialog(&mut self, ctx: &egui::Context)' in mobile
    assert 'panel_open: bool' in mobile and 'fonts_open: bool' in mobile
    assert 'toolbar_shown: false' in mobile
    mobile_toolbar = mobile.split('    pub fn toolbar(&mut self, parent: &mut egui::Ui) -> bool', 1)[1].split('    pub fn handle_menu(&mut self, action: u8)', 1)[0]
    # Optional toolbar controls remain visible whenever the user opens it,
    # while the published Help dialog remains available without that toolbar.
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
    assert 'pub fn toolbar(&mut self, parent: &mut egui::Ui) -> bool' in mobile
    assert 'pub fn sync_toolbar_preference(&mut self, visible: bool)' in mobile
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
    assert 'PDFCRAFT_ANDROID_TRACKPAD_DIAGNOSTICS' in bridge
    assert 'public boolean dispatchGenericMotionEvent(android.view.MotionEvent event)' in bridge
    assert 'return super.dispatchGenericMotionEvent(event)' in bridge
    assert 'event.getAxisValue(50)' in bridge and 'event.getAxisValue(51)' in bridge
    assert 'PDFCRAFT_ANDROID_CURSOR_FEEDBACK' in bridge
    assert 'status.put("cursorRequests", pdfCursorRequests.get())' in bridge
    assert 'status.put("cursorApplied", pdfCursorApplied.get())' in bridge
    assert 'public String pdfTrackpadStatus()' in bridge
    assert 'public void pdfApplyAdaptiveCursor(int type)' in bridge
    assert 'PDF_FONT_SCAN_MAX_BYTES = 4L * 1024 * 1024 * 1024' in bridge
    assert 'PDF_FONT_SCAN_MAX_FILES = 5000' in bridge
    assert 'PDF_FONT_SCAN_MAX_FOLDERS = 10000' in bridge
    assert 'pdfCopyFont(font, name, scanBytes)' in bridge
    assert 'PDF_RELEASES_API + page' in bridge
    assert 'if (conn != null) conn.disconnect();' in bridge
    assert 'PDFCraft-v' in bridge and '-arm64-release.apk' in bridge
    assert 'pdfCompareVersions(latest, installed) > 0' in bridge
print('PASS: embedded Python syntax, guarded patches, idempotence, Android generator, identity/version and Help bridge')
