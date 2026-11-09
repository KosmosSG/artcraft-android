"""Cheap Android.24 overlay regression checks: no Android SDK/CI minutes."""
from pathlib import Path
import tempfile
import unittest

from patch_android24_startup_menu import patch, patch_winit, install_backend_hook


class Android24Overlay(unittest.TestCase):
    def test_preflight_overlay_does_not_change_keyboard_or_save_dialog(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            j = root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
            d = root / "source/vectorcraft/crates/ui-egui/src/widgets/dropdowns.rs"
            j.parent.mkdir(parents=True)
            d.parent.mkdir(parents=True)
            j.write_text(
                "KEYBOARD_SAFE\n"
                "splashHandler.postDelayed(this::dismissStartupCover, 120);\n"
                "    private void dismissStartupCover() {\n"
                "SAVE_DIALOG_SAFE\n"
            )
            d.write_text("POPUP_SAFE .wheel_scroll_multiplier(egui::vec2(1.0, 1.0))")
            patch(root)
            java = j.read_text()
            self.assertIn("KEYBOARD_SAFE", java)
            self.assertIn("SAVE_DIALOG_SAFE", java)
            self.assertIn("vcAndroid24RevealNativeBuffer", java)
            self.assertIn("android24_buffer_probe_timeout", java)
            self.assertNotIn("splashHandler.postDelayed(this::dismissStartupCover, 120);", java)
            self.assertIn("POPUP_SAFE", d.read_text())
            self.assertIn("egui::vec2(1.0, 0.90)", d.read_text())
            with self.assertRaises(ValueError):
                patch(root)  # Refuse accidental double application.

    def test_final_vendored_backend_patch_keeps_gesture_routing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = root / "src/platform_impl/android/mod.rs"
            p.parent.mkdir(parents=True)
            p.write_text(
                "Classification::TwoFingerSwipe => PadGesture::Scroll\n"
                "unclassified_pad\n"
                "x: (current.x - previous.x).clamp(-48.0, 48.0),\n"
                "y: (current.y - previous.y).clamp(-48.0, 48.0),\n"
                "let factor = factor.clamp(0.94, 1.06);\n"
            )
            patch_winit(root)
            native = p.read_text()
            self.assertIn("Classification::TwoFingerSwipe", native)
            self.assertIn("unclassified_pad", native)
            self.assertEqual(native.count("clamp(-160.0, 160.0)"), 2)
            self.assertIn("factor.clamp(0.75, 1.33)", native)
            with self.assertRaises(ValueError):
                patch_winit(root)

    def test_builder_hook_only_changes_disposable_builder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = root / "lib/build-common.sh"
            p.parent.mkdir(parents=True)
            p.write_text('python3 "$ROOT/tools/vectorcraft_backend_stability.py" "$SRC/vendor/winit"\n')
            install_backend_hook(root)
            sh = p.read_text()
            self.assertIn("vectorcraft_backend_stability.py", sh)
            self.assertIn("vectorcraft_android24.py", sh)
            self.assertLess(sh.index("vectorcraft_backend_stability.py"),
                            sh.index("vectorcraft_android24.py"))
            self.assertTrue((root/"tools/vectorcraft_android24.py").is_file())
            with self.assertRaises(ValueError):
                install_backend_hook(root)

    def test_test_only_workflow_gates(self):
        root = Path(__file__).resolve().parents[2]
        path = root/".github/workflows/vectorcraft-android24-test-apk.yml"
        source = path.read_text()
        for required in (
            "investigation/vectorcraft-android24-startup-input-20261109",
            "VERSION_NAME: 0.21.0-android.24",
            "VERSION_CODE: '16783384'",
            "patch_android24_startup_menu.py",
            "com.artcraft.vectorcraft.test",
            "builder/build.sh -vectorcraft --noupdate",
            "!=" + 'os.environ["ORIGINAL_CERT"]',
            "Delete disposable builder signing materials",
        ):
            self.assertIn(required, source)
        self.assertNotIn("gh release create", source)
        self.assertNotIn("workflow_dispatch: { inputs: production_sign", source)


if __name__ == "__main__":
    unittest.main()
