import unittest
from pathlib import Path
import tempfile
from prepare_builder import prepare


class VersionValidation(unittest.TestCase):
    def test_rejects_unqualified_version_and_invalid_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            for version, code in [('0.10.0', 16800001), ('0.10.0-android.0', 1), ('0.10.0-android.1', 0), ('0.10.0-android.1', 2100000001)]:
                with self.subTest(version=version, code=code), self.assertRaises(ValueError):
                    prepare(Path(directory), version, code)


if __name__ == '__main__':
    unittest.main()
