import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile
from prepare_builder import prepare
from verify_apk import verify

CERT = 'a' * 64
BADGING = "package: name='com.artcraft.vectorcraft' versionCode='16790001' versionName='0.14.0-android.1'\nlaunchable-activity: name='com.artcraft.vectorcraft.VectorCraftActivity'\n"
SIGNATURE = 'Signer #1 certificate SHA-256 digest: ' + CERT


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.apk = self.root / 'app.apk'
        with zipfile.ZipFile(self.apk, 'w') as z:
            z.writestr('lib/arm64-v8a/libvectorcraft_android.so', b'fixture')

    def check(self, signature=SIGNATURE, badging=BADGING):
        with patch('subprocess.check_output', side_effect=[signature, badging]):
            return verify(str(self.apk), 'aapt', 'apksigner', '0.14.0-android.1', 16790001, CERT)

    def test_valid_identity(self):
        self.assertEqual(self.check()['device_validation'].split(':')[0], 'pending')

    def test_wrong_signer_rejected(self):
        with self.assertRaises(ValueError):
            self.check(signature=SIGNATURE.replace(CERT, 'b' * 64))

    def test_wrong_package_and_version_rejected(self):
        for old, new in [('com.artcraft.vectorcraft', 'com.artcraft.photocraft'), ('16790001', '1'), ('0.14.0-android.1', '0.14.0')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.check(badging=BADGING.replace(old, new))

    def test_missing_launcher_rejected(self):
        with self.assertRaises(ValueError):
            self.check(badging=BADGING.split('launchable-activity:')[0])

    def test_unsigned_apk_failure_propagates(self):
        import subprocess
        with patch('subprocess.check_output', side_effect=subprocess.CalledProcessError(1, 'apksigner')):
            with self.assertRaises(subprocess.CalledProcessError):
                verify(str(self.apk), 'aapt', 'apksigner', '0.14.0-android.1', 16790001, CERT)

    def test_missing_native_library_rejected(self):
        with zipfile.ZipFile(self.apk, 'w'):
            pass
        with self.assertRaises(ValueError):
            self.check()

    def test_invalid_version_values_do_not_modify_builder(self):
        for version, code in [('0.14.0', 1), ('0.14.0-android.0', 1), ('0.14.0-android.1', 0)]:
            with self.subTest(version=version, code=code), self.assertRaises(ValueError):
                prepare(self.root, version, code)

    def test_unknown_builder_rejected_before_write(self):
        (self.root / 'lib').mkdir()
        script = self.root / 'lib/build-common.sh'
        script.write_text('unreviewed builder')
        with self.assertRaises(ValueError):
            prepare(self.root, '0.14.0-android.1', 16790001)
        self.assertEqual(script.read_text(), 'unreviewed builder')
