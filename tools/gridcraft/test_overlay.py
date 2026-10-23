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
        self.assertIn('egui::Panel::bottom("gridcraft.android.suite_tools_dock")', rust)
        self.assertIn('egui::CollapsingHeader::new("GridCraft Tools  ·  Fonts / Updates / Shortcuts")', rust)
        self.assertIn(".default_open(false)", rust)
        self.assertIn("visuals.dark_mode = false;", rust)
        self.assertIn("visuals.override_text_color", rust)
        self.assertIn("egui::Color32::from_rgb(247, 250, 248)", rust)
        self.assertIn("egui::Margin::symmetric(12, 8)", rust)
        # Bottom panels consume screen space before the workbook canvas is drawn.
        overlay = (SOURCE / "overlay.py").read_text()
        self.assertIn("self.tools.ui(ui, &mut self.inner);", overlay)
        self.assertNotIn("egui::Window::new", rust)
        self.assertIn("ui.spinner()", rust)
        self.assertIn("check_started_at", rust)
        self.assertIn("Update check timed out.", rust)
        self.assertIn("ui.ctx().request_repaint_after", rust)
        self.assertNotIn("gh release create", rust)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", java)

    def test_bottom_tools_show_hide_persists_and_restores_without_floating_window(self):
        rust = (SOURCE / "gridcraft_tools.rs").read_text()
        java = (SOURCE / "GridCraftJavaMethods.java.inc").read_text()
        # The native addon reads an app-private preference and provides a
        # tiny anchored restore affordance when the full tools dock is hidden.
        for expected in (
            'gcToolsPanelVisible', 'gcSetToolsPanelVisible',
            'panel_visible: bool', 'panel_loaded: bool',
            'fn read_panel_visible(&self)', 'fn write_panel_visible(&self, visible: bool)',
            'self.set_panel_visible(false)', 'self.set_panel_visible(true)',
            'egui::Panel::bottom("gridcraft.android.suite_tools_restore")',
            'egui::Panel::bottom("gridcraft.android.suite_tools_dock")',
            'Show GridCraft Tools ▲', 'Hide Panel ▼',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, rust)
        self.assertIn('getBoolean("bottom_tools_visible", false)', java)
        self.assertIn('putBoolean("bottom_tools_visible", visible).apply()', java)
        self.assertLess(rust.index('if !self.panel_visible {'), rust.index('// The spreadsheet uses a light workbook UI.'))
        self.assertNotIn('egui::Window::new', rust)
        # Showing/hiding tools must not interrupt the Java font or updater queues.
        self.assertIn('self.tools.poll();', (SOURCE / "overlay.py").read_text())
        self.assertIn('gcCheckForUpdates()', java)
        self.assertIn('gcImportFont()', java)

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
        self.assertIn('getFilesDir(), ".local/share/fonts"', java)
        self.assertIn("gcStartupChecksEnabled", java)
        self.assertIn("view.zoom", rust)
        self.assertIn("sheet.next", rust)
        self.assertNotIn("photocraft-v", java)
        self.assertNotIn("photocraft", rust.lower())
        self.assertNotIn("KEYSTORE", java)
        self.assertNotIn("DELETE /repos", java)
        self.assertNotIn("installPackage", java)

if __name__ == "__main__":
    unittest.main()
