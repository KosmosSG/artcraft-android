"""GridCraft v0.15 owner-requested regression guards (source-only, no APK)."""
from pathlib import Path
import hashlib
import unittest

ROOT = Path(__file__).resolve().parents[2]
ADDONS = Path(__file__).resolve().parent / "android_addons"
ICON = ROOT / "assets/gridcraft/launcher-user-20261103.png"


class GridCraftOwnerRequests(unittest.TestCase):
    def test_owner_uploaded_icon_is_pinned_for_android_ui_and_launcher(self):
        png = ICON.read_bytes()
        self.assertTrue(png.startswith(bytes.fromhex("89504e470d0a1a0a")))
        self.assertEqual(hashlib.sha256(png).hexdigest(),
                         "e35af23c45ee75e1e026374c7b2458ac9f616cc82ffe39465f9c0ad3f3aeb7b2")
        port = (ROOT / "tools/gridcraft/port_v0150_ui.py").read_text()
        workflow = (ROOT / ".github/workflows/gridcraft-v0150-test-once.yml").read_text()
        self.assertIn('gridcraft-approved-mark.png', port)
        self.assertIn("GRIDCRAFT_ANDROID_USER_ICON_V2", port)
        self.assertIn('egui::Popup::menu(&gc_button).show(', port)
        self.assertIn('image::load_from_memory(include_bytes!(', port)
        self.assertIn('launcher-user-20261103.png', workflow)
        self.assertIn('e35af23c45ee75e1e026374c7b2458ac9f616cc82ffe39465f9c0ad3f3aeb7b2', workflow)

    def test_dark_mode_explicit_toggle_uses_native_persisted_command(self):
        menu = (ADDONS / "GridCraftNativeMenu.rs.inc").read_text()
        self.assertIn('ui.checkbox(&mut dark, "Dark mode")', menu)
        self.assertIn('app.run_or_alert("view.darkMode", json!({}))', menu)
        self.assertIn('theme_choices(app, ui);', menu)

    def test_font_scan_covers_5000_and_remains_4_gib_budget(self):
        java = (ADDONS / "GridCraftJavaMethods.java.inc").read_text()
        self.assertIn('GC_MAX_SHARED_FONTS = 5000', java)
        self.assertIn('GC_MAX_SHARED_DIRS = 5000', java)
        self.assertIn('dirs++ < GC_MAX_SHARED_DIRS', java)
        self.assertIn('imported < GC_MAX_SHARED_FONTS', java)
        self.assertIn('4L * 1024 * 1024 * 1024', java)
        self.assertIn('new byte[64 * 1024]', java)
        self.assertIn('artcraft-shared-staging', java)
        self.assertIn('gcDeleteTree(previous)', java)

    def test_escape_latched_for_hardware_key_before_ime_state_sync(self):
        java = (ADDONS / "GridCraftJavaMethods.java.inc").read_text()
        begin = java.index('if (!gcDialogActive && code == android.view.KeyEvent.KEYCODE_ESCAPE')
        end = java.index('int action = code == android.view.KeyEvent.KEYCODE_D', begin)
        block = java[begin:end]
        self.assertIn('gcEscapePending.set(true)', block)
        self.assertIn('if (gcEditorActive)', block)
        self.assertIn('gcDialogKeys.add(code)', block)
        self.assertNotIn('if (gcEditorActive && !gcDialogActive', block)
        self.assertIn('return super.dispatchKeyEvent(event);', java)

    def test_gpu_renderer_and_touch_gestures_remain_upstream_owned(self):
        # Native wgpu is configured by the pinned builder; our staging overlay
        # must not replace normal Android touch event translation.
        overlay = (ADDONS / "overlay.py").read_text()
        menu = (ADDONS / "GridCraftNativeMenu.rs.inc").read_text()
        self.assertNotIn('handle_touch_event', overlay)
        self.assertNotIn('MotionAction::', overlay)
        self.assertIn('wgpu GPU', menu)
        self.assertIn('Vulkan preferred', menu)


if __name__ == "__main__":
    unittest.main()
