"""Fail-closed tests for the pinned WordCraft 0.14 Android builder shim."""
import tempfile
import unittest
from pathlib import Path
from workspace_v014 import (
    OFFICIAL, PINNED_WIN, BUILDER_ANCHOR, SAFE_GUARD,
    EGUI_VENDOR_START, EGUI_VENDOR_END,
    WINIT_VENDOR_START, WINIT_VENDOR_END, ANR_ACTIVITY_START,
    OLD_EGUI_DEP, preserve_egui_winit_and_winit, apply,
)

# Exercise the dangerous entrypoints on a minimal build-common fixture.
LAUNCHER = """    if saf:
        entry = f'''//! Generated Android launcher for {title}.
    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());
'''
    else:
        entry = f'''//! Generated Android launcher for {title}.
    egui_winit::android_activity::set_activity(android_app.activity_as_ptr());
'''
"""
SHELL = (
    BUILDER_ANCHOR + "\n    echo arboard\nfi\n\n" +
    EGUI_VENDOR_START + "\n    echo old-egui\n" +
    EGUI_VENDOR_END + "\n" +
    WINIT_VENDOR_START + "\n    echo old-winit\n" +
    WINIT_VENDOR_END + "\n" + ANR_ACTIVITY_START + "\n" +
    OLD_EGUI_DEP + "\n" + LAUNCHER
)
MANIFEST = (
    "[workspace.dependencies]\n" + OFFICIAL + "\n\n" +
    "[patch.crates-io]\n" + PINNED_WIN + "\n"
)


class TestV014Compatibility(unittest.TestCase):
    def make_tree(self, root: Path):
        shell = root / "lib/build-common.sh"
        manifest = root / "source/wordcraft/Cargo.toml"
        shell.parent.mkdir(parents=True)
        manifest.parent.mkdir(parents=True)
        shell.write_text(SHELL)
        manifest.write_text(MANIFEST)
        return shell, manifest

    def test_preserves_upstream_forks_without_disabling_other_apps(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            shell, manifest = self.make_tree(base)
            apply(base)
            result = shell.read_text()
            self.assertIn(SAFE_GUARD, result)
            self.assertIn('if [[ "$APP" != "wordcraft" ]]; then\n' +
                          EGUI_VENDOR_START, result)
            self.assertIn('if [[ "$APP" != "wordcraft" ]]; then\n' +
                          WINIT_VENDOR_START, result)
            self.assertIn("egui-winit = \"{'0.37' if app == 'wordcraft' else '0.36'}\"", result)
            self.assertIn("{egui_android_registration}", result)
            self.assertIn('mkdir -p "$SRC/vendor"\n' + ANR_ACTIVITY_START, result)
            self.assertEqual(result.count('mkdir -p "$SRC/vendor"\n' + ANR_ACTIVITY_START), 1)
            self.assertIn(PINNED_WIN, manifest.read_text())
            self.assertEqual(result.count("set_activity(android_app.activity_as_ptr())"), 1)

    def test_rejects_missing_pinned_fork_without_modifying_builder(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            shell, manifest = self.make_tree(base)
            manifest.write_text(manifest.read_text().replace(PINNED_WIN, ""))
            before = shell.read_text()
            with self.assertRaises(ValueError):
                apply(base)
            self.assertEqual(shell.read_text(), before)

    def test_rejects_changed_builder_before_write(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            shell, _ = self.make_tree(base)
            shell.write_text(shell.read_text().replace(WINIT_VENDOR_START, "echo renamed"))
            before = shell.read_text()
            with self.assertRaises(ValueError):
                apply(base)
            self.assertEqual(shell.read_text(), before)

    def test_rejects_missing_egui_036_manifest_anchor(self):
        with self.assertRaises(ValueError):
            preserve_egui_winit_and_winit(SHELL.replace(OLD_EGUI_DEP, ""), MANIFEST)


if __name__ == "__main__":
    unittest.main()
