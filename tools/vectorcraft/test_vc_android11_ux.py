"""Android.11 source-level preservation and input/startup regression checks.

These cheap guards execute before native compilation. Runtime behavioural
and hardware tests remain separate; source markers are not device proof.
"""
from pathlib import Path
import unittest

from patch_vc_icon_menu_v021 import patch_sources

ROOT = Path(__file__).resolve().parents[2]
STABILITY = ROOT / "tools/vectorcraft/patch_stability_v021.py"
MENU = ROOT / "tools/vectorcraft/patch_vc_icon_menu_v021.py"
SCROLL = ROOT / "tools/vectorcraft/patch_smooth_menu_scroll_v021.py"
WORKFLOW = ROOT / ".github/workflows/vectorcraft-stability-test-apk.yml"


class VectorCraftAndroid11Guards(unittest.TestCase):
    def test_close_chords_are_explicitly_dispatched_once_and_unsaved_is_deferred(self):
        text = STABILITY.read_text()
        self.assertIn('Some("app.quit")', text)
        self.assertIn('Some("file.close")', text)
        self.assertIn("modifiers.command || modifiers.ctrl", text)
        self.assertIn('if !self.inner.session.tool_wants_text()', text)
        self.assertIn("self.inner.run(command, serde_json::json!({}))", text)
        self.assertIn("if let Err(error) = self.bridge.end_type_editing()", text)
        self.assertIn("android_save_changes_key(app, ctx) { return; }", text)
        # This is a code generator: the replacement places the modal handler
        # before the viewport focus gate in the GENERATED Rust, not the Python
        # source's argument-string order.
        self.assertIn("if !(ctx.input(|input| input.focused)", text)
        self.assertNotIn('app.run("ui.dialog.confirm"', text)

    def test_ime_bridge_does_not_capture_normal_letters_or_user_text(self):
        text = STABILITY.read_text()
        for marker in (
            "vcPollHiddenImeClose", "poll_hidden_ime_close",
            "KeyEvent.KEYCODE_W || key == KeyEvent.KEYCODE_Q",
            "imeView.hasFocus()", "event.isCtrlPressed()",
            "return super.dispatchKeyEvent(event);",
            "last_type_editing", "if self.last_type_editing && !editing_now",
        ):
            self.assertIn(marker, text)

    def test_launcher_menu_has_gridcraft_style_groups_and_real_upstream_theme_prefs(self):
        source = MENU.read_text()
        for marker in (
            'ui.set_min_width(272.0)', 'ui.menu_button("App Updates"',
            'ui.menu_button("Appearance"', '"uiBrightness"',
            'ui.menu_button("Diagnostics"', 'ui.button("About VectorCraft")',
        ):
            self.assertIn(marker, source)
        menus = "pub use bar::menu_bar;\n"
        bar = '.filter(|(title, _)| *title != "VectorCraft").collect();'
        chrome = (
            '                let (r, _) = ui.allocate_exact_size(vec2(MARK, MARK), Sense::hover());\n'
            '                crate::brand::paint_mark(ui, r);\n'
            '                ui.add_space(6.0);'
        )
        m, b, c = patch_sources(menus, bar, chrome)
        self.assertGreaterEqual(m.count("About VectorCraft"), 1)
        self.assertIn('&& *title != "Vc"', b)
        self.assertIn('menus::android_vc_menu(app, &mark)', c)

    def test_cold_start_waits_for_editor_contrast_not_first_clear(self):
        text = STABILITY.read_text()
        self.assertIn("verifiedNativeFrames >= 2", text)
        self.assertIn("max - min >= 24", text)
        self.assertIn("startupCover == null", text)
        self.assertIn("coverDeadlineMs", text)
        self.assertIn('startupStage("first_painted_editor")', text)

    def test_menu_scroll_uses_egui_and_native_vulkan_without_extra_raw_filter(self):
        stability = STABILITY.read_text()
        scrolling = SCROLL.read_text()
        self.assertIn("smooth_menu(root)", stability)
        self.assertIn("wheel_scroll_multiplier", scrolling)
        self.assertIn("request_repaint_after", scrolling)
        self.assertIn("self.menu_scroll.apply(ctx, raw);", stability)
        self.assertIn("// egui is the only scroll integrator", stability)

    def test_workflow_is_android11_disposable_arm64_only(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.11", workflow)
        self.assertIn("VERSION_CODE: '16783371'", workflow)
        self.assertIn("com.artcraft.vectorcraft.test", workflow)
        self.assertIn("Behavioral gates on generated code before ARM64 compilation", workflow)
        self.assertIn("Delete disposable builder signing materials", workflow)
        self.assertNotIn("gh release create", workflow)


if __name__ == "__main__":
    unittest.main()
