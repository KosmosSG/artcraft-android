"""Android.8 recursive SAF font scan source guards."""
from pathlib import Path
import unittest


class Android8RecursiveFonts(unittest.TestCase):
    def test_recursive_scan_is_bounded_and_supports_collections(self):
        src = Path("tools/designcraft/support/font_methods.java").read_text()
        for required in (
            'pending.addLast(documentId)', 'seen.add(parentId)',
            'visitedFolders < 5000', 'count < 5000',
            'lower.endsWith(".ttc")',
            'first == \'t\' && second == \'t\'',
            '2L * 1024 * 1024 * 1024',
            'StandardCopyOption.ATOMIC_MOVE',
            'getPersistedUriPermissions()',
        ):
            self.assertIn(required, src)
        self.assertNotIn('count < 200', src)
        self.assertIn('64L * 1024 * 1024', src)


if __name__ == "__main__":
    unittest.main()
