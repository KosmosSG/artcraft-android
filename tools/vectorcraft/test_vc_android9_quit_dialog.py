"""VectorCraft Android.9 regression gates — D/C/S, Ctrl+Q, startup facts.

The Android wrapper must never bypass upstream unsaved-document callbacks
nor steal text input while a different dialog is open.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class VectorCraftAndroid9QuitDialog(unittest.TestCase):
    def test_dcs_raw_physical_events_ignore_stale_ime_focus_only_in_unsaved_modal(self):
        script=(ROOT/"tools/vectorcraft/patch_android_unsaved_shortcuts_v020.py").read_text()
        self.assertIn("d.kind == crate::unsaved::KIND && !after_panel && !rejected",script)
        self.assertIn("i.events.iter().any",script)
        self.assertIn("physical_key, pressed: true, repeat: false",script)
        self.assertIn("*physical_key == Some(key)",script)
        self.assertIn("pressed(egui::Key::C)",script)
        self.assertIn("pressed(egui::Key::D)",script)
        self.assertIn("pressed(egui::Key::S)",script)
        self.assertNotIn("&& !egui::Popup::is_any_open(ctx)",script)
        self.assertNotIn("!ctx.text_edit_focused() && ctx.input",script)
        for preserved in ('crate::unsaved::confirm(app)', "Don't Save (D)",
                          "Save (S)", "Cancel (C)"):
            self.assertIn(preserved,script)

    def test_ctrl_q_defers_android_finish_until_upstream_quit_status(self):
        rust=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for item in ('key: egui::Key::Q, pressed: true',
                     '(modifiers.command || modifiers.ctrl) && !modifiers.alt',
                     'self.inner.run("app.quit", serde_json::json!({}))',
                     'self.inner.ui.status == "quit"',
                     'self.bridge.finish_android_after_quit()',
                     'jni_str!("vcFinishAfterQuit")'):
            self.assertIn(item,rust)
        self.assertIn("public void vcFinishAfterQuit()",java)
        self.assertIn("finishAndRemoveTask();",java)
        self.assertIn("if (isFinishing() || isDestroyed()) return;",java)
        self.assertLess(rust.index('self.inner.run("app.quit", serde_json::json!({}))'),
                        rust.index('self.inner.ui.status == "quit"'))
        self.assertNotIn("finishAndRemoveTask();",rust)

    def test_preserve_confirmed_tool_shortcuts_fonts_and_adaptive_cursor(self):
        rust=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        scan=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        for item in ("canvas_hardware_command(", "CanvasHardwareCommand::Selection",
                     "CanvasHardwareCommand::Type", "CanvasHardwareCommand::Pen",
                     "restore_tool_key_text(raw, allow_letters)",
                     "adaptive_cursor::native_pointer_icon("):
            self.assertIn(item,rust)
        self.assertIn("MAX_FONTS = 5000",scan)
        self.assertIn("MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",scan)
        self.assertIn("VERSION_NAME: 0.21.0-android.9",workflow)
        self.assertIn("VERSION_CODE: '16783369'",workflow)
        self.assertIn("com.artcraft.vectorcraft.test",workflow)
        self.assertIn("Delete disposable builder signing materials",workflow)
        self.assertNotIn("gh release create",workflow)


if __name__=="__main__": unittest.main()
