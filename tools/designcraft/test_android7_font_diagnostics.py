"""Source guards for Android.7 font diagnostics and safe cache integration."""
from pathlib import Path
import unittest


class Android7FontDiscoveryGuards(unittest.TestCase):
    def test_scan_diagnostics_count_sources_without_mutating_fonts(self):
        src = Path("tools/designcraft/support/tablet.rs").read_text()
        self.assertIn("Android font scan diagnostics", src)
        self.assertIn('"/system/fonts"', src)
        self.assertIn('"/product/fonts"', src)
        self.assertIn('("Imported", "imported")', src)
        self.assertIn('("Shared SAF cache", "shared")', src)
        self.assertIn("font files only", src)
        self.assertIn('app.run("font.reload"', src)

    def test_document_catalog_adds_android_directories_without_replacing_xdg(self):
        from prepare_builder import patch_designcraft_font_catalog
        base = '''fn system_font_dirs() {
        dirs.extend(unix_font_dirs(home.as_deref(), xdg_data_home.as_deref()));
}'''
        patched = patch_designcraft_font_catalog(base)
        self.assertIn('if cfg!(target_os = "android")', patched)
        self.assertIn('["/system/fonts", "/product/fonts"]', patched)
        self.assertIn('dirs.extend(unix_font_dirs(', patched)
        self.assertEqual(patched.count('/system/fonts'), 1)
        self.assertEqual(patched.count('dirs.extend(["/system/fonts", "/product/fonts"]'), 1)
        with self.assertRaises(ValueError):
            patch_designcraft_font_catalog("new upstream API")

    def test_android6_shortcuts_remain_in_place(self):
        src = Path("tools/designcraft/support/tablet.rs").read_text()
        self.assertIn('("Undo", "edit.undo")', src)
        self.assertIn('("Redo", "edit.redo")', src)
        self.assertIn('("Save", "file.save")', src)


if __name__ == "__main__":
    unittest.main()
