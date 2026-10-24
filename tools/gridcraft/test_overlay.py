"""GridCraft-only overlay contract tests; no SDK, signing secrets or APK required."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

FOLDER = Path(__file__).resolve().parent
SOURCE = FOLDER / "android_addons"

def load_overlay():
    spec = importlib.util.spec_from_file_location("gridcraft_overlay", SOURCE / "overlay.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

class GridCraftOverlayTests(unittest.TestCase):
    def fixture(self, root: Path, package="com.artcraft.gridcraft.candidate"):
        stage = root / "gridcraft-android.artcraft-staging"
        (stage / "src").mkdir(parents=True)
        (stage / "java" / Path(*package.split("."))).mkdir(parents=True)
        (stage / "src/lib.rs").write_text("""
mod ime_bridge;
struct AndroidShell {
    probe: InputProbe,
}
fn new(app: AndroidApp) -> Self {
    let ime = ime_bridge::ime::ImeBridge::new(&app);
    Self { app, probe: InputProbe::default(), }
}
fn logic(&mut self) {
    self.poll_file_picker();
}
fn ui(&mut self, ui: &mut egui::Ui) {
    system_fonts::install_system_fonts(ui.ctx());
}
""")
        (stage / "Cargo.toml").write_text('[package.metadata.android]\npackage = "com.artcraft.gridcraft.candidate"\n')
        (stage / "java" / Path(*package.split(".")) / "GridCraftActivity.java").write_text("""
public final class GridCraftActivity extends NativeActivity {
    void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    }
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
    }
}
""")
        return stage

    def test_gridcraft_overlay_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.fixture(Path(tmp))
            load_overlay().apply_overlay(stage, "com.artcraft.gridcraft.candidate", SOURCE)
            rust = (stage / "src/lib.rs").read_text()
            java = (stage / "java/com/artcraft/gridcraft/candidate/GridCraftActivity.java").read_text()
            cargo = (stage / "Cargo.toml").read_text()
            self.assertIn("mod gridcraft_tools;", rust)
            self.assertIn("self.tools.poll();", rust)
            self.assertIn("self.tools.ui(ui, &mut self.inner);", rust)
            self.assertIn("let tools = gridcraft_tools::GridCraftTools::new(&app);", rust)
            self.assertLess(rust.index("let tools = "), rust.index("Self { app"))
            self.assertIn("gcHandleActivityResult", java)
            self.assertIn("gcStartIfEnabled();", java)
            self.assertIn("gcSelectSharedFolder()", java)
            self.assertIn("gcCheckForUpdates()", java)
            self.assertIn('name = "android.permission.INTERNET"', cargo)
            self.assertTrue((stage / "src/gridcraft_tools.rs").is_file())
            with self.assertRaises(RuntimeError):
                load_overlay().apply_overlay(stage, "com.artcraft.gridcraft.candidate", SOURCE)

    def test_font_import_and_git_release_checker_match_suite_contract(self):
        java = (SOURCE / "GridCraftJavaMethods.java.inc").read_text()
        rust = (SOURCE / "gridcraft_tools.rs").read_text()
        for feature in ("gcImportFont()", "gcSelectSharedFolder()", "gcRefreshSharedFolder()",
                        "gcCheckForUpdates()", "gcStartupChecksEnabled()", "gcSetStartupChecks(",
                        "gcPollResult()", "android.permission"):
            # Android permission is added by the overlay, not the Java fragment.
            if feature != "android.permission":
                with self.subTest(feature=feature):
                    self.assertIn(feature, java)
        self.assertIn('("GridCraft-v" + version + "-arm64-v8a.apk")', java)
        self.assertIn('"uploaded".equals(asset.optString("state"))', java)
        self.assertIn('release.optBoolean("draft")', java)
        self.assertIn('release.optBoolean("prerelease")', java)
        self.assertIn("gridcraft-v", java)
        self.assertIn("getSharedPreferences", java)
        self.assertIn("getFilesDir()", java)
        self.assertNotIn("egui::Panel::bottom", rust)
        self.assertNotIn("egui::Window::new", rust)
        self.assertIn('egui::Id::new("gridcraft.android.menu.action")', rust)
        self.assertIn('gridcraft.android.menu.update_status', rust)
        self.assertIn('gridcraft.android.menu.font_status', rust)
        self.assertIn('gridcraft.android.menu.checking', rust)
        # Before SheetApp::ui the shell processes commands and publishes status.
        overlay = (SOURCE / "overlay.py").read_text()
        self.assertIn("self.tools.ui(ui, &mut self.inner);", overlay)
        self.assertNotIn("egui::Window::new", rust)
        self.assertIn("ui.spinner()", (SOURCE / "GridCraftNativeMenu.rs.inc").read_text())
        self.assertIn("check_started_at", rust)
        self.assertIn("Update check timed out.", rust)
        self.assertIn("ctx.request_repaint_after", rust)
        self.assertNotIn("gh release create", rust)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", java)

    def test_native_gridcraft_tools_in_existing_menu_without_dock(self):
        rust = (SOURCE / "gridcraft_tools.rs").read_text()
        java = (SOURCE / "GridCraftJavaMethods.java.inc").read_text()
        menu = (SOURCE / "GridCraftNativeMenu.rs.inc").read_text()
        installer = (FOLDER / "install_overlay.py").read_text()
        for marker in (
            'GRIDCRAFT_ANDROID_NATIVE_MENU_V1',
            'ui.menu_button("GridCraft Tools"',
            '"Import TTF / OTF..."',
            '"Select Shared Font Folder..."',
            '"Refresh Shared Fonts"',
            '"Check for GridCraft Updates"',
            '"View verified GitHub Release..."',
            '"Check for updates at startup"',
            '"Previous sheet"', '"Next sheet"', '"Undo"', '"Redo"',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, menu)
        self.assertIn('crates/ui-egui/src/ribbon.rs', installer)
        self.assertIn('source/gridcraft', installer)
        self.assertIn('ribbon_source.count(menu_anchor) != 1', installer)
        self.assertIn('ribbon.write_text(patched_ribbon)', installer)
        self.assertIn('gridcraft.android.menu.action', rust)
        self.assertIn('"startup_on" | "startup_off"', rust)
        self.assertIn('gcStartupChecksEnabled', java)
        self.assertIn('gcImportFont()', java)
        self.assertIn('gcCheckForUpdates()', java)
        self.assertNotIn('egui::Window::new', rust)
        self.assertNotIn('egui::Panel::bottom', rust)
        self.assertNotIn('bottom("gridcraft.android.suite_tools_restore")', menu)
        self.assertNotIn('bottom("gridcraft.android.suite_tools_dock")', menu)
        self.assertNotIn('GridCraftNativeMenu.rs.inc', (SOURCE / "overlay.py").read_text())
        # The Android tools source never needs to change upstream workbook state.
        self.assertIn('self.tools.poll();', (SOURCE / "overlay.py").read_text())

    def test_android_user_fonts_show_up_in_gridcraft_catalog_after_restart(self):
        java = (SOURCE / "GridCraftJavaMethods.java.inc").read_text()
        installer = (FOLDER / "install_overlay.py").read_text()
        # Importer must write to exactly the same HOME user-font directory
        # that the pinned upstream GridCraft catalog scans on next launch.
        self.assertIn('new java.io.File(getFilesDir(), "home/ArtCraft-Fonts")', java)
        self.assertIn('dirs.push(h.join("ArtCraft-Fonts"))', installer)
        self.assertIn("GRIDCRAFT_ANDROID_IMPORTED_FONTS_V1", installer)
        self.assertIn("Fully close and reopen GridCraft", java)
        self.assertIn("gcSend(\"font\", \"ok\"", java)
        self.assertNotIn('new java.io.File(getFilesDir(), ".local/share/fonts")', java)
        self.assertIn('getFilesDir(), "home/ArtCraft-Fonts"', java)

    def test_android_tools_async_notifications_not_hidden_inside_menu(self):
        rust = (SOURCE / "gridcraft_tools.rs").read_text()
        self.assertIn('egui::Area::new(egui::Id::new("gridcraft.android.tools.feedback"))', rust)
        self.assertIn('egui::Order::Foreground', rust)
        self.assertIn('self.notify(text)', rust)
        self.assertIn('self.font_request_pending = true', rust)
        self.assertIn('ctx.request_repaint_after', rust)
        self.assertIn('Update check timed out', rust)
        self.assertNotIn('egui::Panel::bottom', rust)
        self.assertNotIn('egui::Window::new', rust)

    def test_gridcraft_only_icon_foreground_preserves_original_glossy_asset(self):
        installer = (FOLDER / "install_overlay.py").read_text()
        self.assertIn('GRIDCRAFT_APPROVED_ADAPTIVE_FOREGROUND_V1', installer)
        self.assertIn('lib/app_icons.py', installer)
        self.assertIn('if app == "gridcraft" else _foreground(Image, stripped)', installer)
        self.assertIn('art.putalpha(matte)', installer)
        self.assertIn('canvas.alpha_composite(art', installer)
        self.assertIn('icon_script.write_text(icon_source)', installer)

    def test_other_app_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = self.fixture(root)
            wrong = root / "photocraft-android.artcraft-staging"
            stage.rename(wrong)
            with self.assertRaisesRegex(RuntimeError, "other than GridCraft"):
                load_overlay().apply_overlay(wrong, "com.artcraft.photocraft", SOURCE)

    def test_source_no_shared_key_or_release_write(self):
        rust = (SOURCE / "gridcraft_tools.rs").read_text()
        java = (SOURCE / "GridCraftJavaMethods.java.inc").read_text()
        self.assertIn("gridcraft-v", java)
        self.assertIn("android.intent.action.ACTION_OPEN_DOCUMENT_TREE", java.replace("Intent.ACTION_OPEN_DOCUMENT_TREE", "android.intent.action.ACTION_OPEN_DOCUMENT_TREE"))
        self.assertIn('getFilesDir(), "home/ArtCraft-Fonts"', java)
        self.assertIn("gcStartupChecksEnabled", java)
        self.assertIn("view.zoom", (SOURCE / "GridCraftNativeMenu.rs.inc").read_text())
        self.assertIn("sheet.next", (SOURCE / "GridCraftNativeMenu.rs.inc").read_text())
        self.assertNotIn("photocraft-v", java)
        self.assertNotIn("photocraft", rust.lower())
        self.assertNotIn("KEYSTORE", java)
        self.assertNotIn("DELETE /repos", java)
        self.assertNotIn("installPackage", java)

if __name__ == "__main__":
    unittest.main()
