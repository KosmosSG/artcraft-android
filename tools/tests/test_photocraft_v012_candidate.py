"""Check isolated PhotoCraft v0.12 Test package staging never edits production."""
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from photocraft_v012_candidate import stage, verify, TEST_PACKAGE


class CandidateIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        original = ROOT / "adapters/photocraft"
        target = self.root / "adapters/photocraft"
        target.mkdir(parents=True)
        (target / "Cargo.toml").write_bytes((original / "Cargo.toml").read_bytes())
        java = target / "java/com/artcraft/photocraft"
        java.mkdir(parents=True)
        for name in ("PhotoCraftActivity.java", "PhotoCraftUpdatePolicy.java"):
            (java / name).write_bytes((original / "java/com/artcraft/photocraft" / name).read_bytes())

    def test_candidate_identity(self):
        stage(self.root)
        verify(self.root)
        self.assertIn(TEST_PACKAGE, (self.root / "adapters/photocraft/Cargo.toml").read_text())

    def test_second_stage_is_refused(self):
        stage(self.root)
        with self.assertRaises(ValueError):
            stage(self.root)

    def test_wrong_launcher_is_rejected_before_writes(self):
        p = self.root / "adapters/photocraft/Cargo.toml"
        p.write_text(p.read_text().replace('name = ".PhotoCraftActivity"', 'name = ".OtherActivity"'))
        with self.assertRaises(ValueError):
            stage(self.root)
        self.assertNotIn(TEST_PACKAGE, p.read_text())


if __name__ == "__main__":
    unittest.main()
