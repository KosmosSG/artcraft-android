"""Version-locked, quota-free tests for the generated GridCraft Android shell."""
import tempfile
import unittest
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
OVL = runpy.run_path(str(ROOT / "android_addons/overlay.py"))


def fake_checkout(root: Path, version: str):
    app = root / "apps/gridcraft-android.artcraft-staging"
    app.mkdir(parents=True)
    (root / "Cargo.toml").write_text(
        f'[workspace]\n[workspace.package]\nversion = "{version}"\n'
    )
    (app / "src").mkdir()
    (app / "src/lib.rs").write_text("""mod ime_bridge;
probe: InputProbe,
let ime = ime_bridge::ime::ImeBridge::new(&app);
probe: InputProbe::default(),
self.poll_file_picker();
system_fonts::install_system_fonts(ui.ctx());
self.inner.logic(ctx);
self.inner.ui(ui);
        self.inner.raw_input_hook(raw);
    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());
""")
    (app / "Cargo.toml").write_text(
        '[package]\nname="gridcraft-android"\nversion="0.1.0"\n'
        '[dependencies]\negui-winit = "0.36"\n'
    )
    java_dir = app / "java/com/artcraft/gridcraft/candidate"
    java_dir.mkdir(parents=True)
    (java_dir / "GridCraftActivity.java").write_text("""
class GridCraftActivity {
    void x() {super.onActivityResult(requestCode, resultCode, data);}
    void y() {super.onCreate(savedInstanceState);}
}
""")
    return app


class CandidateShellStaging(unittest.TestCase):
    def stage(self, version):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stage = fake_checkout(base, version)
            target = stage / "Cargo.toml"
            original = target.read_text()
            if version not in ("0.11.1", "0.15.0"):
                with self.assertRaises(RuntimeError):
                    OVL["apply_overlay"](stage, "com.artcraft.gridcraft.candidate", ROOT / "android_addons")
                self.assertEqual(target.read_text(), original)
                return
            OVL["apply_overlay"](stage, "com.artcraft.gridcraft.candidate", ROOT / "android_addons")
            m = target.read_text()
            self.assertIn('egui-winit = "0.37"' if version == "0.15.0"
                          else 'egui-winit = "0.36"', m)
            self.assertIn("mod gridcraft_tools;", (stage / "src/lib.rs").read_text())
            self.assertIn("self.tools.unsaved_dialog(", (stage / "src/lib.rs").read_text())
            self.assertIn("gcHandleActivityResult(requestCode", (
                stage / "java/com/artcraft/gridcraft/candidate/GridCraftActivity.java").read_text())
            # The official 0.37 fork no longer exposes the builder's
            # stale android_activity helper and upstream now passes ctx.
            rust = (stage / "src/lib.rs").read_text()
            if version == "0.15.0":
                self.assertNotIn("egui_winit::android_activity::set_activity(", rust)
                self.assertIn("self.inner.raw_input_hook(ctx, raw);", rust)
                self.assertNotIn("self.inner.raw_input_hook(raw);", rust)
            else:
                self.assertIn("egui_winit::android_activity::set_activity(", rust)
                self.assertIn("self.inner.raw_input_hook(raw);", rust)
            self.assertTrue((stage / "src/gridcraft_tools.rs").is_file())
            with self.assertRaises(RuntimeError):
                OVL["apply_overlay"](stage, "com.artcraft.gridcraft.candidate", ROOT / "android_addons")

    def test_v015_uses_pinned_egui_037_and_stages_android_ime(self):
        self.stage("0.15.0")

    def test_v011_preserves_tested_egui_036(self):
        self.stage("0.11.1")

    def test_unknown_upstream_fails_closed(self):
        self.stage("0.16.0")


if __name__ == "__main__":
    unittest.main()
