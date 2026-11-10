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
# Regression guard: pinned upstream v0.19.0/v0.20.0 must receive the Android IME-reset
# winit overlay; a skipped guard compiled but failed at egui-winit previously.
assert '"\u0024{PDFCRAFT_REF:-}" == "v0.19.0"' in script
assert '"\u0024{PDFCRAFT_REF:-}" == "v0.20.0"' in script, 'v0.19 IME winit overlay was skipped by builder'
assert '|| "\u0024{PDFCRAFT_REF:-}" == "v0.19.0" || "\u0024{PDFCRAFT_REF:-}" == "v0.20.0" ) ]]; then' in script, 'v0.19 Android arboard compatibility guard missing'


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
                       env={**os.environ, 'PDFCRAFT_ANDROID_VERSION_NAME': os.environ.get('PDFCRAFT_ANDROID_VERSION_NAME', '0.19.0-android.5')})
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    scanner = (dst / 'crates/engine/src/text_fonts.rs').read_text()
    assert ']);\n        }\n        if let Some(folder) = std::env::var_os("PDFCRAFT_ANDROID_FONT_DIR")' in scanner
    before = scanner
    run(patch, dst, 'pdfcraft', 'PDFCraft')
    assert (dst / 'crates/engine/src/text_fonts.rs').read_text() == before
    run(generator, root, dst, 'pdfcraft', 'PDFCraft', '35', 'PDFCraft', '', '')
    android = dst / 'apps/pdfcraft-android'
    cargo = tomllib.loads((android / 'Cargo.toml').read_text())
    assert cargo['package']['version'] == os.environ.get('PDFCRAFT_ANDROID_VERSION_NAME', '0.19.0-android.5')
    assert cargo['dependencies']['egui-winit']['path'] == '../../vendor/egui-winit'
    assert cargo['dependencies']['sha2'] == '0.10'
    assert cargo['package']['metadata']['android']['assets'] == 'ocr-assets'
    assert cargo['package']['metadata']['android']['package'] == 'com.artcraft.pdfcraft'
    native = (android / 'src/lib.rs').read_text()
    assert 'modifiers: AndroidModifiers' in native
    assert 'mod pdfcraft_ocr;' in native
    assert 'fn finish_pdfcraft_android_activity(' in native
    assert 'finish_pdfcraft_android_activity(&exit_activity);' not in native
    assert 'jni_str!("pdfFinishNativeLoop")' in native
    assert native.count('finish_pdfcraft_android_activity(') == 2
    on_exit_signature = ('fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>)'
                         if tomllib.loads((dst / 'Cargo.toml').read_text())['workspace']['package']['version'] == '0.20.0'
                         else 'fn on_exit(&mut self)')
    assert on_exit_signature in native
    assert native.index(on_exit_signature) < native.index('let result = eframe::run_native(')
    assert 'self.persist_now();\n        finish_pdfcraft_android_activity(&self.app);' in native
    assert 'vm.attach_current_thread(' in native
    exit_helper = native.split('fn finish_pdfcraft_android_activity(', 1)[1].split('#[unsafe(no_mangle)]', 1)[0]
    assert 'run_on_java_main_thread' not in exit_helper
    # Stale singleTask intents must recreate rather than target a dead native loop.
    java_file = android / 'java' / 'com' / 'artcraft' / 'pdfcraft' / 'PdfCraftActivity.java'
    java_sources = list((android / 'java').rglob('*.java'))
    assert len(java_sources) == 1, java_sources
    java = java_sources[0].read_text()
    # Android.6: validate the generated Activity, not only the extension template.
    assert 'PDFCRAFT_ANDROID6_LIFECYCLE_TRACE' in java
    for callback in ('onPause', 'onStop', 'onDestroy'):
        assert java.count('protected void ' + callback + '()') == 1, callback
        assert 'pdfLifecycleTrace("' + callback + ':before")' in java, callback
        assert 'pdfLifecycleTrace("' + callback + ':after")' in java, callback
    assert 'android.util.Log.i("PDFCraftLifecycle"' in java
    assert 'android.os.Process.myPid()' in java
    assert 'PDFCRAFT_ANDROID_RELAUNCH_STALE_INTENT' in java
    assert 'if (pdfNativeLoopFinished)' in java
    assert 'recreate();' in java
    assert 'public void pdfFinishNativeLoop()' in java
    # Android.7 targeted fix: never remove the task while an Activity relaunch races.
    assert 'finishAndRemoveTask();' not in java
    assert 'pdfLifecycleTrace("finish:before")' in java
    assert 'finish();' in java
    assert 'pdfNativeLoopFinished = true;' in java
    assert 'PDFCRAFT_ANDROID4_LIFECYCLE_HANDOFF' in java
    assert 'runOnUiThread(finishNativeActivity);' in java
    assert 'std::process::exit(' not in native
    assert 'PDFCRAFT_ANDROID4_SYNC_EXIT_JNI' in (root/'lib/build-common.sh').read_text()
    assert 'tools/pdfcraft/android_native_exit_patch.py' in (root/'lib/build-common.sh').read_text()
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
    assert 'PDFCRAFT_ANDROID_PC_APPEARANCE' in menu
    assert 'ui.menu_button("Appearance", |ui|' in menu
    assert 'self.set_theme_preference(preference)' in menu
    assert 'PDFCRAFT_ANDROID_INK_PRESSURE_CAPTURE' in (dst / 'crates/ui-egui/src/tools/comments/input.rs').read_text()
    assert 'PDFCRAFT_ANDROID_INK_PRESSURE_STATE' in (dst / 'crates/ui-egui/src/tools/comments/state.rs').read_text()
    assert 'PDFCRAFT_ANDROID_INK_PRESSURE_COMMIT' in (dst / 'crates/ui-egui/src/tools/comments/input.rs').read_text()
    assert 'PDFCRAFT_ANDROID4_LOW_LATENCY_INK' in (dst / 'crates/ui-egui/src/tools/comments/input.rs').read_text()
    assert 'PDFCRAFT_ANDROID_HONOR_FINGER_MOUSE' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'pub fn android_tools_visible(&self) -> bool' in menu
    assert 'pub fn set_android_tools_visible(&self, visible: bool)' in menu
    assert 'view.push(self.menu_item(ANDROID_TOOLS, None))' in menu
    assert 'PDFCRAFT_ANDROID_HELP_REQUEST' in menu
    assert 'PDFCRAFT_ANDROID_ICON_MENU' in menu
    assert 'crate::android_approved_brand::paint(ui.painter(), rect.shrink(2.0))' in menu
    assert '"Import Fonts…"' in menu and '"Check for Updates…"' in menu
    assert '"Automatic update check…"' not in menu
    assert 'PDFCRAFT_ANDROID_DECKCRAFT_APP_UPDATES' in menu
    assert 'ui.menu_button("App Updates", |ui|' in menu
    assert '"✓  Toggle Update Check at Startup"' in menu
    assert '"    Toggle Update Check at Startup"' in menu
    assert 'egui::Id::new("pdfcraft.android.startup.enabled")' in menu
    assert '"About PDFCraft"' in menu
    assert '"Trackpad diagnostics…"' not in menu
    assert '"GPU diagnostics…"' not in menu
    assert '"android.import_fonts"' not in menu
    assert 'PDFCRAFT_ANDROID_BIDIRECTIONAL_PINCH' in (root / 'tools/pdfcraft/android_input_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_PINCH' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_GESTURE_AXES_34' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_SCROLL_LOCK' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID_TRACKPAD_PHASED_SCROLL' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
    assert 'PDFCRAFT_ANDROID4_TRACKPAD_NO_BUTTON_NO_CLICK' in (root / 'tools/pdfcraft/android_trackpad_patch.py').read_text()
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
    assert 'PDFCRAFT_ANDROID_ACTIVITY_CLEANUP' in bridge
    assert 'pdfBackground.shutdownNow();' in bridge
    assert 'protected void onDestroy()' in bridge
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
    # The version shown in Updates and About must come from PackageManager,
    # never from the former 0.19.0-android.3 test candidate.
    assert 'public String pdfInstalledBuildInfo()' in bridge
    assert 'getPackageManager().getPackageInfo(getPackageName(), 0)' in bridge
    assert 'PDFCRAFT_ANDROID_RUNTIME_BUILD_IDENTITY' in bridge
    assert 'boolean standardPackage = "com.artcraft.pdfcraft".equals(getPackageName())' in bridge
    assert 'if (standardPackage) {' in bridge
    assert 'Separate PDFCraft test package: ' in bridge
    assert 'read_installed_build_info()' in mobile
    assert 'jni_str!("pdfInstalledBuildInfo")' in mobile
    assert 'Installed: PDFCraft {} ({package_type})' in mobile
    assert 'Version {}' in mobile
    assert 'Android package: {}' in mobile
    assert '0.19.0-android.3' not in mobile
    assert 'Temporary signing — not a production release' not in mobile
    # Generated Java Activity must contain the exact runtime metadata bridge.
    assert 'public String pdfInstalledBuildInfo()' in java
    # PhotoCraft-style native Android Toast feedback: routine checks must
    # never open the modal, while a new stable release retains Download/Install.
    assert 'enum Action { ImportFont, SelectFolder, RefreshFonts, CheckUpdates { manual: bool } }' in mobile
    assert 'jni_str!("pdfCheckForUpdates"), jni_sig!("(Z)V")' in mobile
    assert 'self.check_updates(true);' in mobile
    assert 'if self.startup_check { self.check_updates(false); }' in mobile
    assert 'self.updates_open = false;' in mobile.split('fn check_updates(&mut self, manual: bool)', 1)[1].split('pub fn poll(', 1)[0]
    assert 'if self.update_asset_url.is_some() {' in mobile
    assert 'self.updates_open = true;' in mobile.split('if self.update_asset_url.is_some() {', 1)[1]
    assert 'public void pdfCheckForUpdates(boolean manual)' in bridge
    assert 'private void pdfUpdateToast(String message)' in bridge
    assert 'android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show()' in bridge
    assert 'if (manual) pdfUpdateToast("Checking for PDFCraft updates…");' in bridge
    assert 'PDFCraft is up to date (' in bridge
    assert "Couldn't check PDFCraft updates:" in bridge
    assert 'public void pdfCheckForUpdates(boolean manual)' in java
    assert 'android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show()' in java
    assert 'ui.button("Download APK")' in mobile and 'self.install_download()' in mobile
    # On fresh installations startup checks default ON; an existing OFF
    # preference remains OFF. Toggling gives a native bottom Toast.
    assert 'mobile.read_startup_setting().unwrap_or(true)' in mobile
    assert 'startup_check: true, first_frame: true' in mobile
    assert 'egui::Id::new("pdfcraft.android.startup.enabled"), self.startup_check' in mobile
    assert 'let enabled = !self.startup_check;' in mobile
    assert 'match self.save_startup_setting(enabled)' in mobile
    assert 'getBoolean(PDF_STARTUP_UPDATE_PREF, true)' in bridge
    assert 'pdfUpdateToast("PDFCraft update checks at startup: " + (enabled ? "ON" : "OFF"))' in bridge
    assert 'if self.startup_check { self.check_updates(false); }' in mobile
print('PASS: embedded Python syntax, guarded patches, idempotence, Android generator, identity/version and Help bridge')
