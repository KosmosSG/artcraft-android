"""WordCraft android.8 acceptance-guard tests for source-level wiring.

These tests catch accidental loss of the requested icon, raw D/C/S intercept
and font scan limits. Device interactions still require MagicPad testing.
"""
from pathlib import Path
import ast
import unittest

HERE = Path(__file__).resolve().parent
BUILD = HERE / "patch_builder.py"
RIBBON = HERE / "ribbon_android.rs.inc"
RUST = HERE / "wordcraft_android.rs"
JAVA = HERE / "WordCraftExtension.java.inc"
WORKFLOW = HERE.parent.parent / ".github" / "workflows" / "wordcraft-v014-candidate.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class WordCraftDeviceFixes(unittest.TestCase):
    def test_stylus_hover_and_curve_smoothing_is_isolated_and_regression_guarded(self):
        from pathlib import Path
        base = Path(__file__).parent
        java = text(JAVA)
        native = text(RUST)
        build = text(BUILD)
        overlay = (base / "patch_stylus_ink.py").read_text()
        curve = (base / "stylus_curve.rs.inc").read_text()
        for marker in ("wcStylusHoverPosition()", "wcTakeStylusTrail()",
                       "getHistoricalX(i, h)", "getHistoricalPressure(i, h)",
                       "wcPenPeakPressure", "wcPenLastContactPressure"):
            self.assertIn(marker, java)
        for marker in ("inject_stylus_motion(&self", "wc_stylus.hover_pos",
                       "wc_stylus.path_samples"):
            self.assertIn(marker, native)
        for marker in ("wc_stylus_samples", "apply_stylus_ink", "stylus_curve.rs.inc"):
            self.assertIn(marker, build)
        for marker in ("WC_ANDROID_STYLUS_HOVER_CURSOR_V1", "wc_smooth_stroke",
                       "get_temp::<[f32; 2]>", "painter.circle_stroke",
                       "source = one(source, old_pen, new_pen"):
            self.assertIn(marker, overlay)
        self.assertIn("WC_STYLUS_CURVE_SMOOTHING_V1", curve)
        self.assertNotIn("secrets.", build)
        self.assertIn("wcRejectPalm(", java)

    def test_builder_shim_parses_and_wires_raw_keys_before_clipboard(self):
        s = text(BUILD)
        ast.parse(s)
        self.assertIn('wc_raw_dcs = ', s)
        self.assertIn('self.wc.capture_unsaved_keys(self.inner.android_unsaved_dcs_active(), ctx, raw)', s)
        self.assertIn('{wc_raw_dcs}{wc_trackpad_scroll}{wc_touch_pan}{wc_stylus_samples}        self.handle_clipboard_shortcuts(raw);', s)

    def test_approved_icon_is_derived_from_launcher_and_not_unrelated_asset(self):
        s = text(BUILD)
        self.assertIn('wordcraft-approved-192.png', s)
        self.assertIn('resize((40, 40)', s)
        self.assertIn('wordcraft-android-menu-icon.rgba', s)
        menu = text(RIBBON)
        self.assertIn('include_bytes!("wordcraft-android-menu-icon.rgba")', menu)
        self.assertIn('egui::ColorImage::from_rgba_unmultiplied([40, 40], rgba)', menu)
        self.assertIn('egui::Button::image', menu)
        self.assertIn(').frame(false)).on_hover_text', menu)
        self.assertNotIn('egui::ImageButton::new', menu)
        self.assertIn('egui::Popup::menu(&button)', menu)
        self.assertNotIn('ui.menu_button("ArtCraft"', menu)
        self.assertIn('place WordCraft launcher icon menu at top left of tab strip', s)

    def test_raw_key_dcs_preempts_editor_and_does_not_override_pending_choice(self):
        s = text(RUST)
        self.assertIn('pub fn capture_unsaved_keys(&self, active: bool, ctx: &egui::Context, raw: &mut egui::RawInput)', s)
        for k in ("D", "C", "S"):
            self.assertIn('egui::Key::' + k, s)
        self.assertIn('raw.events.retain', s)
        self.assertIn('if active && !modifiers.any()', s)
        self.assertIn('if d.get_temp::<u8>(id).is_none()', s)
        self.assertIn('ctx.request_repaint();', s)
        java = text(JAVA)
        self.assertIn('wcDialogAction.compareAndSet(0, choice)', java)
        self.assertIn('if (!active) { wcDialogAction.set(0); return 0; }', java)

    def test_physical_dcs_text_and_ime_fallback_during_modal(self):
        rust = text(RUST)
        java = text(JAVA)
        for x in (
            'egui::Event::Key { key, physical_key, pressed, repeat, modifiers, .. }',
            '(*physical_key).unwrap_or(*key)',
            'egui::Event::Text(text) if allow_text_choice',
            'egui::Event::Ime(egui::ImeEvent::Commit(text)) if allow_text_choice',
            'let allow_text_choice = active && !text_modifiers.any();',
            'egui::Event::ModifiersChanged(modifiers) => Some(*modifiers)',
            'egui::Event::Key { modifiers, .. } => Some(*modifiers)',
            'WC_DCS_DIAG raw_choice=',
        ):
            self.assertIn(x, rust)
        self.assertNotIn('raw.modifiers', rust)
        self.assertIn('wcDialogAction.compareAndSet(0, choice)', java)

    def test_ctrl_shift_s_uses_existing_wordcraft_save_as_saf(self):
        rust = text(RUST)
        java = text(JAVA)
        for x in (
            '!active && actual_key == egui::Key::S',
            'modifiers.ctrl && modifiers.shift',
            '!modifiers.alt && !modifiers.mac_cmd',
            'wordcraft.shortcut.save_as',
            'self.call_bool("wcTakeSaveAs")',
            'app.has_document()',
            'app.save_as_dialog();',
            'WC_SHORTCUT_DIAG raw_ctrl_shift_s',
        ):
            self.assertIn(x, rust)
        for x in (
            'public boolean wcTakeSaveAs()',
            '!wcDialogActive && event.isCtrlPressed()',
            'event.isShiftPressed() && key == android.view.KeyEvent.KEYCODE_S',
            'wcSaveAs.set(1)',
        ):
            self.assertIn(x, java)
        self.assertNotIn('app.run("file.saveAs", serde_json::json!({}))', rust)

    def test_shared_scan_caps_5000_files_and_4_gib_and_stays_async(self):
        s = text(JAVA)
        for anchor in (
            'private static final int WC_MAX_FONTS = 5_000;',
            'private static final int WC_MAX_FOLDERS = 20_000;',
            'private static final long WC_MAX_FONT_TOTAL_BYTES = 4L * 1024 * 1024 * 1024;',
            'io.execute(() -> wcScanFontTree(Uri.parse(saved)));',
            'while (!pending.isEmpty() && scannedFolders < WC_MAX_FOLDERS && copied < WC_MAX_FONTS',
            'while (cursor.moveToNext() && copied < WC_MAX_FONTS',
            'pending.size() + seen.size() < WC_MAX_FOLDERS',
            'total > WC_MAX_SINGLE_FONT_BYTES',
            'copiedBytes + total > WC_MAX_FONT_TOTAL_BYTES',
            'result.put("maxFonts", WC_MAX_FONTS)',
        ):
            self.assertIn(anchor, s)
        self.assertNotIn('copied < 150', s)
        self.assertNotIn('copiedBytes < 200L * 1024 * 1024', s)
        self.assertIn('for _ in 0..8 {', text(RUST))
        self.assertIn('5,000 files / 4 GiB maximum', text(RIBBON))

    def test_two_finger_trackpad_scroll_is_native_precise_and_not_touchscreen(self):
        java = text(JAVA)
        rust = text(RUST)
        build = text(BUILD)
        for line in (
            'dispatchGenericMotionEvent(android.view.MotionEvent event)',
            'event.getActionMasked() == android.view.MotionEvent.ACTION_SCROLL',
            'android.view.InputDevice.SOURCE_TOUCHPAD',
            'android.view.InputDevice.SOURCE_MOUSE',
            'android.view.MotionEvent.AXIS_HSCROLL',
            'android.view.MotionEvent.AXIS_VSCROLL',
            'getScaledHorizontalScrollFactor()',
            'getScaledVerticalScrollFactor()',
            'wcTakeTrackpadScroll()',
            'synchronized (wcScrollLock)',
            'return super.dispatchGenericMotionEvent(event);',
        ):
            self.assertIn(line, java)
        for line in (
            'pub fn inject_trackpad_scroll(',
            'self.call_string("wcTakeTrackpadScroll")',
            'let scale = ctx.pixels_per_point();',
            'egui::Event::PointerMoved',
            'egui::Event::MouseWheel {',
            'egui::MouseWheelUnit::Point',
            'egui::MouseWheelSource::Trackpad',
            'egui::TouchPhase::Move',
            'ctx.request_repaint();',
        ):
            self.assertIn(line, rust)
        self.assertIn('{wc_raw_dcs}{wc_trackpad_scroll}{wc_touch_pan}{wc_stylus_samples}        self.handle_clipboard_shortcuts(raw);', build)
        self.assertIn("wc_trackpad_scroll = ", build)
        # No JNI bridge is created for other apps; no fake touchscreen drag events.
        self.assertIn("if app == 'wordcraft' else ''", build)
        self.assertNotIn("egui::Event::Touch {", rust)


    def test_modal_esc_and_hardware_ime_paths_cancel_without_discarding(self):
        java, rust, build = text(JAVA), text(RUST), text(BUILD)
        for marker in (
            'public boolean wcHandleHardwareShortcut(android.view.KeyEvent event)',
            'wcHandleHardwareShortcut(event)',
            'public boolean wcHandleImeChoice(CharSequence text)',
            'wcDialogAction.compareAndSet(0, choice)',
            'key == android.view.KeyEvent.KEYCODE_ESCAPE ? 2 : 0',
            'WC_DCS_DIAG physical_choice=',
        ):
            self.assertIn(marker, java)
        self.assertIn('wcHandleImeChoice(text)', build)
        self.assertIn('wcHandleHardwareShortcut(event)', build)
        self.assertIn('wcDialogKeys.contains(key)', java)
        self.assertIn('active && actual_key == egui::Key::Escape', rust)
        self.assertIn('choice = Some(2)', rust)
        self.assertIn('if (!active) { wcDialogAction.set(0); return 0; }', java)

    def test_ctrl_q_asks_before_quitting_unsaved_documents(self):
        java, rust = text(JAVA), text(RUST)
        self.assertIn('key == android.view.KeyEvent.KEYCODE_Q', java)
        self.assertIn('public boolean wcTakeQuit()', java)
        self.assertIn('wcQuit.set(1)', java)
        self.assertIn('!active && actual_key == egui::Key::Q', rust)
        self.assertIn('self.call_bool("wcTakeQuit")', rust)
        self.assertIn('if app.quit()', rust)
        self.assertIn('egui::ViewportCommand::Close', rust)
        self.assertNotIn('android.os.Process.killProcess', java)

    def test_two_finger_touchscreen_pan_preserves_pinch_zoom(self):
        java, rust, build = text(JAVA), text(RUST), text(BUILD)
        for marker in (
            'dispatchTouchEvent(android.view.MotionEvent event)',
            'event.isFromSource(android.view.InputDevice.SOURCE_TOUCHSCREEN)',
            'event.getPointerCount() == 2',
            'android.view.MotionEvent.ACTION_POINTER_DOWN',
            'android.view.MotionEvent.ACTION_MOVE',
            'wcTouchLastSpan * .025f',
            'return super.dispatchTouchEvent(event);',
            'public String wcTakeTwoFingerPan()',
        ):
            self.assertIn(marker, java)
        self.assertIn('self.call_string("wcTakeTwoFingerPan")', rust)
        self.assertIn('pub fn inject_touch_pan(', rust)
        self.assertIn('wc_touch_pan = ', build)
        self.assertIn('{wc_trackpad_scroll}{wc_touch_pan}', build)
        self.assertNotIn('egui::Event::Touch {', rust)

    def test_copy_a_to_b_uses_system_clipboard_on_copy_and_paste(self):
        build = text(BUILD)
        self.assertIn('egui::OutputCommand::CopyText(text)', build)
        self.assertIn('android_clipboard_set(&self.app, &copy)', build)
        self.assertIn('self.handle_clipboard_shortcuts(raw)', build)
        self.assertNotIn('android_clipboard_set(&self.app, "")', build)


    def test_one_ctrl_v_yields_one_paste_and_preserves_android_clipboard(self):
        rust, build = text(RUST), text(BUILD)
        for piece in (
            'paste_key_held: Cell<bool>',
            'paste_key_held: Cell::new(false)',
            'pub fn deduplicate_clipboard_input(&self, raw: &mut egui::RawInput)',
            'key: egui::Key::V',
            'repeat: false',
            'let fresh_press = paste_down && !was_held',
            'let keep_last = raw.events.iter().rposition(|event| matches!(',
            'let keep = !held_repeat && Some(at) == keep_last',
            'egui::Event::Ime(egui::ImeEvent::Commit(text))',
            'self.paste_key_held.set(false)',
        ):
            self.assertIn(piece, rust)
        self.assertIn("wc_clip_dedupe = ", build)
        self.assertIn("self.wc.deduplicate_clipboard_input(raw);", build)
        self.assertIn("{wc_clip_dedupe}{persist_hook}        {inner_hook}", build)
        self.assertIn("if app == 'wordcraft' else ''", build)
        self.assertIn('android_clipboard_set(&self.app, &copy)', build)
        # Android.6 required Ctrl+V keydown in the same frame; the video shows
        # duplicates when Android/IME delivers a copy without that key event.
        self.assertIn('use std::cell::{Cell, RefCell};', rust)
        self.assertIn('recent_paste: RefCell<Option<(Instant, String)>>', rust)
        self.assertIn('let recent = self.recent_paste.borrow()', rust)
        self.assertIn('let echo_text = current.as_deref().or(recent.as_deref());', rust)
        self.assertIn('Duration::from_millis(110)', rust)
        self.assertIn('!fresh_press', rust)
        self.assertIn('if paste_out > 0', rust)
        self.assertIn('WC_PASTE_DIAG paste_in=', rust)
        self.assertIn('key_suppressed={}', rust)
        self.assertIn('let has_clipboard_paste = current.is_some();', rust)
        self.assertIn('&& (has_clipboard_paste || held_repeat)', rust)
        self.assertIn('duplicate_key_dropped += 1;', rust)
        self.assertIn('key: egui::Key::V, pressed: true, modifiers, ..', rust)
        self.assertIn('let paste_up =', rust)  # Key-up still reaches WordCraft.
        self.assertNotIn('log::info!("WC_PASTE_DIAG {}", text)', rust)

    def test_candidate_build_has_new_test_and_temp_key_not_original(self):
        s = text(WORKFLOW)
        self.assertIn("test_wordcraft_device_fixes.py", s)
        self.assertIn("0.14.0-android.8", s)
        self.assertIn('100014008', s)
        self.assertIn('TEMP-SIGNED-NO-UPGRADE', s)
        self.assertNotIn("0.14.0-android.7", s)


if __name__ == "__main__":
    unittest.main()
