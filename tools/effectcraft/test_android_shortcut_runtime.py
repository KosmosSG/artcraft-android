"""EffectCraft-only hardware Ctrl and D/C/S modal keyboard bridge regressions."""
from pathlib import Path
import unittest
import ast

ROOT = Path(__file__).parent

class ShortcutWiring(unittest.TestCase):
    def test_generated_launcher_python_remains_parseable(self):
        # This catches the exact failure from Actions #41823706603:
        # Rust text.endEdit/log strings were nested in a Python double-quoted
        # generator literal and broke the generated build-common.sh heredoc.
        source = (ROOT / "integrate_updater.py").read_text()
        tree = ast.parse(source)
        generated = [
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and "Changes apply solely to the fully rendered EffectCraft launcher." in node.value.value
        ]
        self.assertEqual(len(generated), 1)
        # The integration replaces double escaped newlines before staging.
        code = generated[0].replace(chr(92) * 2 + "n", chr(92) + "n")
        ast.parse("def builder():" + chr(10) + code)
        self.assertIn('execute("text.endEdit"', code)
        self.assertIn('log::warn!("EffectCraft modal text commit:', code)

    def test_capture_before_ui_dialog_and_text_edit_close(self):
        build = (ROOT / "integrate_updater.py").read_text()
        order = [
            "self.updates.keyboard_shortcuts(&mut self.inner, ui.ctx());",
            "self.inner.android_unsaved_dcs_active() && self.inner.session.state.text_edit.is_some()",
            'self.inner.session.execute("text.endEdit"',
            "self.inner.android_capture_unsaved_dcs(ui.ctx());",
            "self.updates.unsaved_dialog(self.inner.android_unsaved_dcs_active(), ui.ctx());"
        ]
        for item in order: self.assertIn(item, build)
        self.assertTrue(all(build.index(a) < build.index(b) for a,b in zip(order, order[1:])))
    def test_jni_route_keeps_upstream_guard_and_no_raw_unchecked_quit(self):
        rust=(ROOT / "android_updater.rs").read_text()
        for item in ('ecPollPhysicalShortcut', '"file.close"', '"app.quit"',
                     "effectcraft_ui_egui::menus::invoke(inner, ctx,", "inner.dialog.is_some()"):
            self.assertIn(item,rust)
        self.assertNotIn("std::process::exit",rust)
    def test_modal_ime_does_not_mutate_text_and_keep_escape(self):
        p=(ROOT / "integrate_updater.py").read_text()
        self.assertIn("if (ecDialogActive) return true;",p)
        self.assertIn("if (ecDialogActive) return;",p)
        self.assertIn("ecConsumePhysicalShortcut(event)",p)
        self.assertIn("ecConsumeDialogKey(event)",p)
        self.assertIn("event.getKeyCode() == android.view.KeyEvent.KEYCODE_ESCAPE",p)
        self.assertIn("ecDialogAction.compareAndSet(0, action)",p)
if __name__=="__main__": unittest.main()
