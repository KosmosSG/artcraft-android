#!/usr/bin/env python3
"""Static safety contract for staged DesignCraft in-app updater.

Complements (does not replace) cargo-apk2 compilation, APK signature checks
and physical HONOR MagicPad 4 installation/update testing.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/designcraft/support/DesignCraftUpdateDownload.java"
SOURCE = ROOT / "tools/designcraft/support/update_methods.java"
STAGER = ROOT / "tools/designcraft/install_v017_updater.py"
POLICY = ROOT / "tools/designcraft/support/DesignCraftUpdatePolicy.java"


class TestDesignCraftInAppUpdater(unittest.TestCase):
    def test_download_requires_production_identity(self):
        src = HELPER.read_text()
        self.assertIn('PACKAGE.equals(activity.getPackageName())', src)
        self.assertIn('DesignCraftUpdatePolicy.CERT', src)
        self.assertIn('canRequestPackageInstalls()', src)
        self.assertIn('android.permission.REQUEST_INSTALL_PACKAGES', STAGER.read_text())

    def test_security_verification_before_installer_intent(self):
        src = HELPER.read_text()
        self.assertLess(src.index('verifyApk(activity, output, checksum, versionCode, versionName)'),
                        src.index('android.content.Intent.ACTION_VIEW'))
        for mandatory in ('expectedSha', 'getPackageArchiveInfo(', 'getApkContentsSigners()',
                          'getLongVersionCode()', 'lib/arm64-v8a/libdesigncraft_android.so',
                          'FLAG_GRANT_READ_URI_PERMISSION', 'SHA256_CERT.equals(actualCert)'):
            self.assertIn(mandatory, src)
        self.assertIn('android.app.DownloadManager', src)
        self.assertIn('Download in app', SOURCE.read_text())

    def test_preexisting_updater_and_monotonic_version_policy_preserved(self):
        src = SOURCE.read_text()
        self.assertIn('void dcCheckUpdates(boolean manual)', src)
        self.assertIn('DesignCraftUpdatePolicy.validate(', src)
        self.assertIn('DesignCraftUpdatePolicy.newer(', src)
        self.assertIn('manifest.getString("apk_sha256")', src)
        self.assertIn('DesignCraftUpdateDownload.start(', src)
        policy = POLICY.read_text()
        self.assertIn('certificate', policy)
        self.assertIn('candidate > installed', policy)

    def test_source_staging_without_source_replacement(self):
        staged = STAGER.read_text()
        self.assertIn('support / "DesignCraftUpdateDownload.java"', staged)
        self.assertIn('if package == "com.artcraft.designcraft":', staged)
        self.assertIn('tomllib.loads(cargo_text)', staged)
        self.assertIn('Expected one anchor', staged.replace("expected one anchor", "Expected one anchor"))


if __name__ == "__main__":
    unittest.main()
