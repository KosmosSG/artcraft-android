"""PhotoCraft-parity safety tests for the pinned DesignCraft Android candidate."""
import tempfile
from pathlib import Path
import unittest

from menu_overlay import apply


class DesignCraftAndroidParity(unittest.TestCase):
    def test_menu_overlay_is_pinned_and_fail_closed(self):
        pinned = Path("builder/source/designcraft/crates/ui-egui/src/menus.rs")
        self.assertTrue(pinned.is_file(), "Exact pinned upstream menus.rs checkout is required")
        with tempfile.TemporaryDirectory() as temp:
            edited = Path(temp) / "menus.rs"
            edited.write_bytes(pinned.read_bytes())
            original = edited.read_text()
            apply(edited)
            after = edited.read_text()
            self.assertNotEqual(original, after)
            self.assertIn('artcraft_take_android_actions()', after)
            self.assertIn('"Type" => &["app.artcraftImportFont"', after)
            self.assertIn('"Help" => &["help.artcraftCheckUpdates"', after)
            self.assertIn('"Window" => &["window.artcraftShortcutPad"', after)
            self.assertIn('entries.extend(ids.iter().map(|id| cmd_item(id, Value::Null)))', after)
            self.assertIn('entries.push(Item::Sep)', after)
            # Device diagnostic: 23 egui wheel events reached the renderer,
            # but default popup hover gating never moved the menu. Read the raw
            # wheel directly using popup geometry and set a bounded scroll offset.
            self.assertIn('input.raw.events.iter().filter_map', after)
            self.assertIn('egui::Event::MouseWheel { unit, delta, modifiers, .. }', after)
            self.assertIn('previous_rect.contains(pointer)', after)
            self.assertIn('let pointer = pointer_now.or(last_pointer);', after)
            self.assertIn('Option<egui::Pos2>', after)
            self.assertIn('rendered.inner_rect, pointer, touch_last, mouse_last', after)
            self.assertIn('offset = (offset - wheel).clamp', after)
            self.assertIn('rendered.content_size.y - rendered.inner_rect.height()', after)
            self.assertIn('.vertical_scroll_offset(offset)', after)
            self.assertIn('mouse_wheel: false', after)
            self.assertIn('artcraft_menu_scroll_diagnostics()', after)
            self.assertIn('ARTCRAFT_MENU_SCROLL_EVENTS.fetch_add', after)
            self.assertIn('ARTCRAFT_MENU_TOUCH_SCROLL_EVENTS.fetch_add', after)
            self.assertIn('egui::Event::Touch { phase: egui::TouchPhase::Start', after)
            self.assertIn('egui::TouchPhase::Move', after)
            self.assertIn('egui::TouchPhase::End | egui::TouchPhase::Cancel', after)
            self.assertIn('egui::Event::PointerButton { pressed: true', after)
            self.assertIn('egui::Event::PointerMoved(pos)', after)
            self.assertIn('let has_touch = touch_events.iter().any(', after)
            self.assertIn('offset = (offset - finger_delta_y).clamp', after)
            self.assertIn('Option<egui::Pos2>, Option<egui::Pos2>', after)
            self.assertIn('ARTCRAFT_MENU_TOUCH_SCROLL_EVENTS.load', after)
            self.assertIn('drag: egui::containers::scroll_area::DragScroll::Never', after)
            self.assertIn('scroll_bar: true', after)
            self.assertIn('ScrollBarVisibility::VisibleWhenNeeded', after)
            self.assertIn('(ui.ctx().content_rect().height() * 0.72).max(180.0)', after)
            self.assertIn('#[cfg(target_os = "android")]\n    let max_height', after)
            self.assertIn('#[cfg(not(target_os = "android"))]\n        if ui.is_sizing_pass()', after)
            self.assertNotIn('egui::Button::new("▲ Scroll up")', after)
            self.assertNotIn('egui::Button::new("▼ More items")', after)
            self.assertNotIn('vertical_scroll_offset(target)', after)
            self.assertNotIn('designcraft-android-menu-scroll', after)

            self.assertNotIn('entries.splice(0..0, android)', after)
            with self.assertRaises(ValueError):
                apply(edited)

    def test_font_cache_refresh_never_deletes_previous_good_file(self):
        java = Path("tools/designcraft/support/font_methods.java").read_text()
        self.assertIn('dcRestoreSharedFontsOnStartup()', java)
        self.assertIn('getPersistedUriPermissions()', java)
        self.assertIn('new File(cache, "font-" + hash + extension + ".pending")', java)
        self.assertIn('StandardCopyOption.ATOMIC_MOVE', java)
        self.assertIn('if (!validHeader)', java)
        self.assertNotIn('target.delete();', java)

    def test_android_font_cache_is_writable_and_scanned_after_import(self):
        from prepare_builder import patch_android_font_paths
        # Assert against the exact pinned builder file, not an unused suite copy.
        upstream = Path("builder/templates/android/system_fonts.rs").read_text()
        staged = patch_android_font_paths(upstream)
        self.assertIn('std::fs::read_link(&link)', staged)
        self.assertIn('std::fs::remove_file(&link)', staged)
        self.assertIn('std::fs::create_dir_all(&link)', staged)
        self.assertIn('link.join("android-system")', staged)
        self.assertIn('std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));', staged)
        self.assertNotIn('std::env::set_var("XDG_DATA_HOME", &base);', staged)
        with self.assertRaises(ValueError):
            patch_android_font_paths(staged)

        rust = Path("tools/designcraft/support/tablet.rs").read_text()
        java = Path("tools/designcraft/support/font_methods.java").read_text()
        self.assertIn('join(".local/share/fonts/imported")', rust)
        self.assertIn('"home/.local/share/fonts/shared"', java)
        self.assertIn('app.run("font.reload"', rust)
        self.assertIn('dcRestoreSharedFontsOnStartup()', java)

    def test_candidate_java_update_policy_uses_generated_activity_package(self):
        from support.patch_launcher import update_policy_for_activity
        production = Path("tools/designcraft/support/DesignCraftUpdatePolicy.java").read_text()
        for suffix in ("", ".candidate"):
            package = "com.artcraft.designcraft" + suffix
            activity = "package " + package + ";\npublic class DesignCraftActivity {}"
            actual = update_policy_for_activity(activity, production)
            self.assertTrue(actual.startswith("package " + package + ";"))
            self.assertEqual(actual.replace("package " + package + ";",
                                            "package com.artcraft.designcraft;", 1), production)
            # The helper's production-update identity gate is unchanged.
            self.assertIn('!"com.artcraft.designcraft".equals(pkg)', actual)
        with self.assertRaises(ValueError):
            update_policy_for_activity("package com.unknown;", production)

    def test_font_notification_and_persistent_android_toolbar_window_menu(self):
        rust = Path("tools/designcraft/support/tablet.rs").read_text()
        menus = Path("tools/designcraft/menu_overlay.py").read_text()
        launcher = Path("tools/designcraft/support/patch_launcher.py").read_text()
        self.assertIn('window.artcraftAndroidToolbar', menus)
        self.assertIn('ARTCRAFT_ANDROID_ACTIONS.fetch_or(64', menus)
        self.assertIn('if actions & 64 != 0', rust)
        self.assertIn('set_toolbar_visible(!self.toolbar_visible)', rust)
        self.assertIn('android-toolbar-visible', rust)
        self.assertIn('if self.toolbar_visible {', rust)
        self.assertIn('self.show_notification(ui);', rust)
        self.assertIn('designcraft-font-import-notification', rust)
        self.assertIn('format!("Imported font: {name}")', launcher)

    def test_approved_icon_and_top_left_navigation_in_candidate(self):
        builder = Path("tools/designcraft/prepare_builder.py").read_text()
        stage = Path("tools/designcraft/support/apply_approved_branding.py").read_text()
        workflow = Path(".github/workflows/designcraft-font-import-preview.yml").read_text()
        self.assertIn('apply_approved_branding.py', builder)
        self.assertIn('designcraft-approved', builder)
        self.assertIn('approved_branding.check_assets()', stage)
        self.assertIn('approved_branding.apply(builder, source, android, "designcraft")', stage)
        self.assertIn('android_approved_brand::home_button(ui, home)', stage)
        self.assertIn('home_response.clicked()', stage)
        self.assertIn('version +', stage)
        self.assertIn('tools/approved-branding/assets/DesignCraft.png', workflow)
        self.assertIn('verify_approved_candidate.py', workflow)
        self.assertNotIn('tools/designcraft/make_icon.py builder/dc-icon.png', workflow)

    def test_android_trackpad_scroll_reaches_egui_without_menu_pagers(self):
        from support.patch_launcher import append_trackpad_bridge
        base = "package com.artcraft.designcraft.candidate;\npublic final class DesignCraftActivity extends GameActivity {}"
        patched = append_trackpad_bridge(base)
        self.assertIn("dispatchGenericMotionEvent(android.view.MotionEvent event)", patched)
        self.assertIn("android.view.MotionEvent.ACTION_SCROLL", patched)
        self.assertIn("android.view.MotionEvent.AXIS_VSCROLL", patched)
        self.assertIn("android.view.MotionEvent.AXIS_HSCROLL", patched)
        self.assertIn("android.view.MotionEvent.AXIS_GESTURE_SCROLL_X_DISTANCE", patched)
        self.assertIn("android.view.MotionEvent.AXIS_GESTURE_SCROLL_Y_DISTANCE", patched)
        self.assertIn("android.os.Build.VERSION.SDK_INT < 34", patched)
        self.assertIn("dcCaptureGestureScroll(event)", patched)
        self.assertIn("getResources().getDisplayMetrics().density", patched)
        self.assertIn("public synchronized int dcGestureAxisEventCount()", patched)
        self.assertIn("public synchronized int dcGenericMoveCount()", patched)
        self.assertIn("public synchronized int dcTouchMoveCount()", patched)
        self.assertIn("public synchronized long dcLastMotionInfo()", patched)
        self.assertIn("android.view.MotionEvent.AXIS_SCROLL", patched)
        self.assertIn("super.dispatchGenericMotionEvent(event)", patched)
        self.assertIn("public synchronized long dcPollTrackpadScroll()", patched)
        self.assertIn("public synchronized long dcInputEventCounts()", patched)
        self.assertIn("public synchronized int dcTouchpadMoveCount()", patched)
        self.assertIn("super.dispatchTouchEvent(event)", patched)
        with self.assertRaises(ValueError):
            append_trackpad_bridge(patched)

        native = Path("tools/designcraft/support/tablet.rs").read_text()
        launcher = Path("tools/designcraft/support/patch_launcher.py").read_text()
        menus = Path("tools/designcraft/menu_overlay.py").read_text()
        self.assertIn("pub fn poll_trackpad_scroll(", native)
        self.assertIn('jni_sig!("()J")', native)
        self.assertIn('jni_str!("dcPollTrackpadScroll")', native)
        self.assertIn("tablet::poll_trackpad_scroll(&self.app)", launcher)
        self.assertIn("!raw.events.iter().any(|e| matches!(e, egui::Event::MouseWheel", launcher)
        self.assertIn("egui::MouseWheelUnit::Line", launcher)
        self.assertIn("modifiers: egui::Modifiers::NONE", launcher)
        self.assertNotIn("modifiers: raw.modifiers", launcher)
        self.assertIn("ctx.request_repaint_after", launcher)
        self.assertIn("tablet::record_wheel_events(raw, fallback_injected)", launcher)
        self.assertIn("pub fn record_wheel_events(", native)
        self.assertIn('jni_str!("dcInputEventCounts")', native)
        self.assertIn('jni_str!("dcTouchpadMoveCount")', native)
        self.assertIn("Trackpad Input Diagnostics", native)
        self.assertIn("ANDROID_GESTURE_AXES", native)
        self.assertIn("ANDROID_GENERIC_MOVE", native)
        self.assertIn("ANDROID_TOUCH_MOVE", native)
        self.assertIn("ANDROID_LAST_MOTION", native)
        self.assertIn("Last Android motion:", native)
        self.assertIn("window.artcraftInputDiagnostics", menus)
        self.assertNotIn("vertical_scroll_offset(target)", menus)
        self.assertIn("mouse_wheel: false", menus)
        self.assertIn("menu_scroll_diagnostics()", native)
        self.assertIn("Menu wheel events:", native)
        self.assertIn("Menu touch-scroll events:", native)
        self.assertNotIn('egui::Button::new("▲ Scroll up")', menus)
        self.assertNotIn('egui::Button::new("▼ More items")', menus)

    def test_updater_rejects_disposable_test_package(self):
        java = Path("tools/designcraft/support/update_methods.java").read_text()
        self.assertIn('if (!"com.artcraft.designcraft".equals(getPackageName()))', java)
        self.assertIn('dcChecking.compareAndSet(false, true)', java)
        self.assertIn('release.optBoolean("prerelease")', java)
        self.assertNotIn('ACTION_INSTALL_PACKAGE', java)

    def test_touch_pad_is_opt_in_persistent_and_text_safe(self):
        rust = Path("tools/designcraft/support/tablet.rs").read_text()
        self.assertIn('android-shortcuts-enabled', rust)
        self.assertIn('ctx().text_edit_focused()', rust)
        self.assertIn('min_size(egui::vec2(56.0, 44.0))', rust)
        self.assertIn('artcraft_take_android_actions()', rust)


if __name__ == "__main__":
    unittest.main()
