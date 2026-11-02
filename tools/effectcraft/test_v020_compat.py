"""Tests for EffectCraft isolated v0.20 menu and metadata migration guards."""
import tempfile
import unittest
from pathlib import Path

from v020_compat import (
    LEGACY_ANCHOR,
    MODERN_ANCHOR,
    menu_path_and_anchor,
    stage_trial_metadata,
)


class MenuMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def put(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        return dest

    def test_modern_v020_layout(self):
        target = self.put("crates/ui-egui/src/menus/bar.rs", "start\n" + MODERN_ANCHOR + "\nend\n")
        self.put("crates/ui-egui/src/menus.rs", "mod bar;")
        self.assertEqual(menu_path_and_anchor(self.root), (target, MODERN_ANCHOR))

    def test_v016_legacy_layout(self):
        target = self.put("crates/ui-egui/src/menus.rs", "start\n" + LEGACY_ANCHOR + "\nend\n")
        self.assertEqual(menu_path_and_anchor(self.root), (target, LEGACY_ANCHOR))

    def test_unexpected_upstream_fails_closed(self):
        self.put("crates/ui-egui/src/menus/bar.rs", "changed upstream code")
        with self.assertRaisesRegex(RuntimeError, "drift"):
            menu_path_and_anchor(self.root)

    def test_existing_android_hook_rejected(self):
        self.put("crates/ui-egui/src/menus/bar.rs", MODERN_ANCHOR + "\nartcraft.effectcraft.check_updates_requested")
        with self.assertRaisesRegex(RuntimeError, "already injected"):
            menu_path_and_anchor(self.root)


class MetadataMigrationTests(unittest.TestCase):
    def test_trial_metadata_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lib/build-common.sh"
            p.parent.mkdir(parents=True)
            original = 'version_line = f\'version = "{app_version}-android.3"\' if app == "effectcraft" else "version.workspace = true"\nversion_code = 16781315\n'
            p.write_text(original)
            stage_trial_metadata(Path(d))
            revised = p.read_text()
            self.assertIn('{app_version}-android.1', revised)
            self.assertIn('version_code = 16810001', revised)
            self.assertNotIn('version_code = 16781315', revised)
            with self.assertRaisesRegex(RuntimeError, "refuse rewrite"):
                stage_trial_metadata(Path(d))


if __name__ == "__main__":
    unittest.main()
