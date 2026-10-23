"""Regression coverage for the official VectorCraft v0.16 FilePick API change."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class VectorCraftV016FileFilters(unittest.TestCase):
    def test_owned_extensions_borrowed_for_mime_without_saf_regression(self):
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        self.assertIn("exts.first().map(String::as_str)", rust)
        self.assertNotIn("exts.first().copied()", rust)
        self.assertIn("fn mime_for_filters(pick: &FilePick) -> String", rust)
        self.assertIn('.unwrap_or_else(|| "*/*".to_string())', rust)
        for marker in ("vcRequestOpen", "vcRequestSave", "mime_for_extension(ext)"):
            self.assertIn(marker, rust)


if __name__ == "__main__":
    unittest.main()
