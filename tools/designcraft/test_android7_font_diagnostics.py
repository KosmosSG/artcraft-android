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

    def test_android6_shortcuts_remain_in_place(self):
        src = Path("tools/designcraft/support/tablet.rs").read_text()
        self.assertIn('("Undo", "edit.undo")', src)
        self.assertIn('("Redo", "edit.redo")', src)
        self.assertIn('("Save", "file.save")', src)


if __name__ == "__main__":
    unittest.main()
