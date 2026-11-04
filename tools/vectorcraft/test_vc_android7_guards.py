"""VectorCraft Android.7: keyboard focus, dialog mnemonic and menu-scroll gates."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VectorCraftAndroid7Guards(unittest.TestCase):
    def test_dcs_after_ctrl_w_is_modal_only_and_ignores_stale_modifiers(self):
        patch=(ROOT/"tools/vectorcraft/patch_android_unsaved_shortcuts_v020.py").read_text()
        self.assertIn("d.kind == crate::unsaved::KIND",patch)
        self.assertIn("!ctx.text_edit_focused()",patch)
        self.assertIn("i.key_pressed(key)",patch)
        self.assertNotIn("consume_key(egui::Modifiers::NONE, key)",patch)

    def test_physical_keyboard_focus_returns_to_real_surface(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        rust=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in ("findNativeSurface(container)", "nativeSurface.requestFocus()",
                       "if (!imeWanted && imeView != null && imeView.hasFocus())",
                       "this::vcEndTypeEditing"):
            self.assertIn(marker,java)
        for marker in ("self.modifiers = AndroidModifiers::default();",
                       "egui::Event::ModifiersChanged(egui::Modifiers::NONE)"):
            self.assertIn(marker,rust)

    def test_trackpad_egui_menu_low_pass_does_not_modify_canvas(self):
        router=(ROOT/"adapters/vectorcraft/src/android_modifiers.rs").read_text()
        adapter=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in ("pub struct AndroidMenuScrollSmoother",
                       "if !egui::Popup::is_any_open(ctx)",
                       "self.pending += delta * factor",
                       "ctx.request_repaint_after(std::time::Duration::from_millis(16))",
                       "focus_regain_clears_ctrl_even_if_ime_swallowed_key_up",
                       "popup_easing_does_not_touch_canvas_wheel_events"):
            self.assertIn(marker,router)
        self.assertIn("self.menu_scroll.apply(ctx, raw);",adapter)

    def test_working_fonts_and_disposable_release_are_untouched(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        self.assertIn("MAX_FONTS = 5000",java)
        self.assertIn("MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",java)
        self.assertIn("VERSION_NAME: 0.21.0-android.7",workflow)
        self.assertIn("com.artcraft.vectorcraft.test",workflow)
        self.assertIn("Delete disposable builder signing materials",workflow)
        self.assertNotIn("gh release create",workflow)


if __name__=="__main__":
    unittest.main()
