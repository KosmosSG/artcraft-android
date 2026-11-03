"""Source-only regression contracts for DesignCraft's Android device test fixes."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]

class V016InteractionContract(unittest.TestCase):
    def test_debug_only_stager_is_syntactically_valid(self):
        path = ROOT / "tools/designcraft/patch_v016_interactions.py"
        source = path.read_text()
        ast.parse(source, filename=str(path))
        self.assertIn('src.name!="designcraft"', source)
        self.assertIn('android.name!="designcraft-android"', source)
        builder = (ROOT / "tools/designcraft/patch_v016_android.py").read_text()
        self.assertIn("from patch_v016_interactions import ui_source, launcher, java_source", builder)
        self.assertIn("java_source(root, android)", builder)

    def test_shared_font_folder_persisted_and_recursive(self):
        java = (ROOT / "tools/designcraft/support/font_methods.java").read_text()
        stager = (ROOT / "tools/designcraft/patch_v016_interactions.py").read_text()
        ui = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        self.assertIn("Intent.ACTION_OPEN_DOCUMENT_TREE", java)
        self.assertIn("getPersistedUriPermissions()", java)
        self.assertIn("pending.addLast(documentId)", java)
        self.assertIn("count < 5000", java)
        self.assertIn("4L * 1024 * 1024 * 1024", java)
        self.assertIn("new File(appStorageDir(),", stager)
        self.assertIn("takePersistableUriPermission(", stager)
        self.assertIn('kind == "font_folder"', stager)
        self.assertIn("take_android_shared_actions()", ui)
        self.assertIn("Select Shared Font Folder", ui)
        self.assertIn("Refresh Shared Fonts", ui)
        self.assertIn("font.reload", ui)

    def test_hardware_shortcuts_modal_keyboard_and_top_menu(self):
        stager = (ROOT / "tools/designcraft/patch_v016_interactions.py").read_text()
        ui = (ROOT / "tools/designcraft/v016_android.rs").read_text()
        self.assertIn('"Android",', stager)
        self.assertIn("dcUnsavedDialog", stager)
        self.assertIn("dispatchKeyEvent(KeyEvent event)", stager)
        self.assertIn("KEYCODE_ESCAPE", stager)
        # T/V must pass through native dispatch; Java interception caused
        # shortcuts to disappear while the Activity kept focus.
        self.assertNotIn("code == KeyEvent.KEYCODE_T || code == KeyEvent.KEYCODE_V", stager)
        self.assertIn("return super.dispatchKeyEvent(event);", stager)
        self.assertIn('app.select_tool(tool)', ui)
        self.assertIn('egui::Panel::top("artcraft-designcraft-android-tools").show(ui,', ui)
        self.assertIn('designcraft.unsaved.dcs', ui)
        self.assertIn('modifiers.ctrl || modifiers.command', ui)
        self.assertIn('designcraft_ui_egui::menus::close_document(app, None)', ui)
        self.assertIn('app.select_tool("selection")', ui)

    def test_dialog_actions_clear_on_close(self):
        java_stager = (ROOT / "tools/designcraft/patch_v016_interactions.py").read_text()
        self.assertIn('dcDialogAction.set(0);', java_stager)
        self.assertIn('if (!active)', java_stager)
        self.assertIn('ctx.request_repaint();', (ROOT / "tools/designcraft/v016_android.rs").read_text())
        self.assertIn('dcDialogHeld.clear();', java_stager)
        self.assertIn('dc_dialog_action(&self, active: bool)', java_stager)
        self.assertIn('super.dispatchKeyEvent(event);', java_stager)

    def test_next_candidate_version_is_android_3(self):
        version = (ROOT / "tools/designcraft/patch_v016_android.py").read_text()
        self.assertIn('candidate_version = "0.16.0-android.3"', version)
        self.assertIn('APP_VERSION="0.16.0-android.3"', (ROOT / "lib/build-common.sh").read_text())

    def test_no_production_workflow_modified(self):
        workflow = (ROOT / ".github/workflows/designcraft-v016-review.yml").read_text()
        self.assertIn('Experimental ARM64 compile (NOT a release)', workflow)
        self.assertNotIn('softprops/action-gh-release', workflow)

if __name__ == "__main__":
    unittest.main()
