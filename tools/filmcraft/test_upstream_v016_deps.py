"""Offline fail-closed tests for FilmCraft-only v0.16 Cargo patch override."""
from pathlib import Path
import importlib.util
import unittest

SRC = Path(__file__).with_name("stage_v016_builder_deps.py")
spec = importlib.util.spec_from_file_location("stage_v016_builder_deps", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class BuilderDependencyPinTests(unittest.TestCase):
    def fixture(self):
        # A deliberately small copy of the pinned builder's ordered boundaries.
        return ("header\n" + module.EGUI_START +
                "\nmkdir -p \"$SRC/vendor\"\npython3 - \"$SRC/Cargo.toml\" <<'PY'\npass\nPY\n\n" +
                module.EGUI_END + "\nother vendors\n" +
                module.WINIT_START + "\npython3 - \"$SRC/Cargo.toml\" <<'PY'\npass\nPY\n\n" +
                module.WINIT_END + "\n" + module.LAUNCHER_EGUI_OLD + "\n" + module.BUILD_ANCHOR + "\n")

    def test_only_filmcraft_skips_outdated_vendor_and_checks_pins(self):
        source = self.fixture()
        output = module.patch_text(source)
        self.assertIn('if [[ "$APP" != "filmcraft" ]]; then\n' + module.EGUI_START, output)
        self.assertIn('if [[ "$APP" != "filmcraft" ]]; then\n' + module.WINIT_START, output)
        self.assertIn("PYFILMCRAFTDEPS", output)
        self.assertIn(module.LAUNCHER_EGUI_NEW, output)
        self.assertNotIn(module.LAUNCHER_EGUI_OLD, output)
        # Confirm other ArtCraft apps still use the pinned builder's 0.36.
        self.assertIn("if app == 'filmcraft' else '0.36'", output)
        self.assertIn(module.W_REV, output)
        self.assertIn(module.E_REV, output)
        self.assertEqual(output.count(module.BUILD_ANCHOR), 1)
        self.assertIn("other vendors", output)
        self.assertEqual(output.count("if [[ \"$APP\" != \"filmcraft\" ]]; then"), 2)

    def test_fails_closed_on_source_drift_and_double_application(self):
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            module.patch_text(self.fixture().replace(module.WINIT_START, "changed"))
        with self.assertRaisesRegex(ValueError, "already staged"):
            module.patch_text(module.patch_text(self.fixture()))

    def test_fails_closed_on_wrong_source_order(self):
        fixture = self.fixture().replace(module.WINIT_START, "REPLACED")
        fixture = fixture.replace(module.EGUI_START, module.WINIT_START)
        fixture = fixture.replace("REPLACED", module.EGUI_START)
        with self.assertRaisesRegex(ValueError, "order changed"):
            module.patch_text(fixture)

if __name__ == "__main__":
    unittest.main()
