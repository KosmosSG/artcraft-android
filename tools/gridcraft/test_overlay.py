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
