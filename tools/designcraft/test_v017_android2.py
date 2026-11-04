"""DesignCraft Android.2 controls and adaptive pointer regression gates.

Static/source verification only; compilation and HONOR MagicPad 4 testing
must still be done before the release is considered working.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DesignCraftAndroid2Input(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = ROOT / "tools/designcraft"
        cls.java = (d / "patch_v017_interactions.py").read_text()
        cls.native = (d / "v016_android.rs").read_text()
        cls.pointer = (d / "fork_v020_adaptive_pointer_icon.rs").read_text()
        cls.context = (d / "fork_v020_android_activity.rs").read_text()
        cls.overlay = (d / "overlay_v017_cursor.py").read_text()
        cls.wheel = (d / "overlay_winit_android_mouse.py").read_text()
        cls.builder = (ROOT / "lib/build-common.sh").read_text()
        cls.stager = (d / "patch_v017_android.py").read_text()
        cls.workflow = (ROOT / ".github/workflows/designcraft-v017-review.yml").read_text()

    def test_physically_queued_tool_keys(self):
        expected = {
            "T": "type", "V": "selection", "H": "hand", "Z": "zoom",
            "A": "directSelection", "P": "pen", "N": "pencil",
            "F": "rectangleFrame", "M": "rectangle", "B": "contentCollector",
        }
        for key, tool in expected.items():
            self.assertIn(f"KEYCODE_{key}", self.java)
            self.assertIn(f'Some("{tool}")', self.native)
        self.assertIn("ctx.text_edit_focused()", self.native)
        self.assertIn("app.session.wants_text()", self.native)
        self.assertIn("event.hasNoModifiers()", self.java)

    def test_escape_and_unsaved_modal_dispatch(self):
        for name in ("dcTakeEscapeAction", "dcTakeCloseAction",
                     "dcTakeToolAction", "dcUnsavedDialog"):
            self.assertIn(name, self.java)
        self.assertIn("dcDialogHeld.clear()", self.java)
        self.assertIn('egui::Key::BrowserBack', self.native)
        self.assertIn('bridge.dc_escape_action()', self.native)
        self.assertIn('bridge.dc_close_action()', self.native)
        self.assertIn("designcraft.unsaved.dcs", self.native)

    def test_launcher_icon_replaces_android_top_level_menu(self):
        self.assertIn('include_image!("dc-launcher-icon.png")', self.native)
        self.assertIn('menu_custom_button', self.native)
        self.assertIn('mipmap-xxxhdpi/ic_launcher.png', self.stager)
        for text in ("Import Fonts", "Select Shared Font Folder", "Refresh Shared Fonts",
                     "Reload Font Catalog", "Check Updates", "Startup Update Check",
                     "Android Tools"):
            self.assertIn(text, self.native)
        self.assertNotIn('"Android",\n        &[', self.java)

    def test_cursor_is_fork_port_not_entire_app_merge(self):
        self.assertIn('pub fn pointer_icon_type', self.pointer)
        for icon in ('C::Text', 'C::PointingHand', 'C::ResizeHorizontal'):
            self.assertIn(icon, self.pointer)
        self.assertIn("pub fn set_activity", self.context)
        self.assertIn('egui-winit', self.overlay)
        self.assertIn('pointer_icon::apply(cursor_icon)', self.overlay)
        self.assertIn('overlay_v017_cursor.py', self.builder)
        self.assertIn('android_activity::set_activity', self.stager)
        self.assertIn('src.name != "designcraft"', (ROOT/"tools/designcraft/install_v017_updater.py").read_text())

    def test_trackpad_axes_and_compatible_package(self):
        self.assertIn("enable_motion_axis(Axis::Vscroll)", self.wheel)
        self.assertIn("enable_motion_axis(Axis::Hscroll)", self.wheel)
        self.assertIn('0.17.0-android.2', self.stager)
        self.assertIn("fix/designcraft-v017-android2-input-cursor-20261104", self.workflow)
        self.assertNotIn("action-gh-release", self.workflow)
        self.assertNotIn("secrets.", self.workflow)


if __name__ == "__main__":
    unittest.main()
