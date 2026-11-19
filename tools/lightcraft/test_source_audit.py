import subprocess
import tempfile
import unittest
from pathlib import Path
from audit_source import check_checkout, check_files, digest


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Preflight Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'engine.rs').write_text('original engine\n')
        self.git('add', 'engine.rs')
        self.git('commit', '-qm', 'fixture')
        self.head = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True)

    def test_clean_exact_checkout(self):
        check_checkout(self.root, self.head)

    def test_wrong_commit_rejected(self):
        with self.assertRaisesRegex(ValueError, 'immutable commit'):
            check_checkout(self.root, '0' * 40)

    def test_unstaged_engine_change_rejected(self):
        (self.root / 'engine.rs').write_text('changed engine\n')
        with self.assertRaisesRegex(ValueError, 'Tracked source'):
            check_checkout(self.root, self.head)

    def test_staged_engine_change_rejected(self):
        (self.root / 'engine.rs').write_text('changed engine\n')
        self.git('add', 'engine.rs')
        with self.assertRaisesRegex(ValueError, 'Tracked source'):
            check_checkout(self.root, self.head)

    def test_reviewed_file_hash(self):
        expected = {'engine.rs': digest(self.root / 'engine.rs')}
        check_files(self.root, expected)
        (self.root / 'engine.rs').write_text('changed API\n')
        with self.assertRaisesRegex(ValueError, 'differs'):
            check_files(self.root, expected)


if __name__ == '__main__':
    unittest.main()
