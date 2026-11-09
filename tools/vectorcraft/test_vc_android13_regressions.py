"""VectorCraft Android.13 precompilation safeguards for five MagicOS regressions."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT/"tools/vectorcraft"

class Vectorcraft13Safeguards(unittest.TestCase):
    def test_native_keys_held_by_ime_do_not_block_v_t_after_escape(self):
        source=(TOOLS/"patch_android13_recovery.py").read_text()
        self.assertIn("final boolean canvasKey = mode == 1",source)
        self.assertIn("if (mode == 1 && imeWanted) vcEndTypeEditing();",source)
        self.assertIn("self.inner.select_tool(tool_id)",source)
        self.assertIn("!editing && !field_focused && !composing && !modal",source)

    def test_save_dialog_uses_real_commands_before_egui_focus_gate(self):
        source=(TOOLS/"patch_android13_recovery.py").read_text()
        self.assertIn("pub fn android_owner_unsaved_key",source)
        self.assertIn("self.inner.android_owner_unsaved_key(key)",source)
        self.assertIn('dialog, "discard".into(), json!(true)',source)
        self.assertIn("crate::dialogs::confirm(self)",source)
        self.assertIn("crate::dialogs::cancel(self)",source)
        tests=(TOOLS/"android_stability_tests.rs").read_text()
        self.assertIn("android_stability_direct_owner_key_bridge_handles_save_cancel_discard",tests)
        self.assertIn("android_stability_native_owner_key_bridge_never_drops_failed_save",tests)

    def test_activity_finish_is_guarded_by_real_quit(self):
        recovery=(TOOLS/"patch_android13_recovery.py").read_text()
        self.assertIn('finishAndRemoveTask();',recovery) # old-source match only
        self.assertIn("finish();",recovery)
        adapter=(TOOLS/"patch_stability_v021.py").read_text()
        self.assertIn('self.inner.ui.status == "quit"', (ROOT/"adapters/vectorcraft/src/lib.rs").read_text())
        self.assertIn("recovery13(root)",adapter)

    def test_legacy_sixteen_second_black_fallback_is_removed(self):
        recovery=(TOOLS/"patch_android13_recovery.py").read_text()
        self.assertIn("firstFrameProbeStartMs = System.currentTimeMillis()",recovery)
        self.assertIn("splashHandler.postDelayed(this::probeFirstPresentedFrame, 700)",recovery)
        self.assertIn("nativeEditorReady = true", (TOOLS/"patch_stability_v021.py").read_text())

    def test_photo_style_scroll_not_double_damped(self):
        source=(TOOLS/"patch_android13_menu_scroll.py").read_text()
        self.assertIn("wheel_scroll_multiplier(egui::vec2(1.0, 1.0))",source)
        self.assertIn("let hovered_menu = egui::Popup::is_any_open(ctx)",source)
        self.assertIn("request_repaint_after",source)
        self.assertNotIn("CanvasTouchGestures",source)

    def test_disposable_version_and_no_release(self):
        workflow=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.21",workflow)
        self.assertIn("VERSION_CODE: '16783381'",workflow)
        self.assertIn("patch_android13_recovery.py",workflow)
        self.assertIn("patch_android13_menu_scroll.py",workflow)
        self.assertIn("com.artcraft.vectorcraft.test",workflow)
        self.assertIn("Delete disposable builder signing materials",workflow)
        self.assertNotIn("gh release create",workflow)

if __name__ == "__main__":
    unittest.main()
