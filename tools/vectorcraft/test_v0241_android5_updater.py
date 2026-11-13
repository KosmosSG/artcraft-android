"""Source-scope security & contract checks for VectorCraft Android.5 updater.

Runs before NDK compilation; optionally inspects generated Android staging tree.
Never contacts GitHub or invokes the installer in CI.
"""
from pathlib import Path
import os, unittest

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / "tools/vectorcraft/VectorCraftUpdateInstaller.java"
PATCH = ROOT / "tools/vectorcraft/patch_v0241_android5_updater.py"

class UpdateSecurity(unittest.TestCase):
    def test_package_and_signer_guards(self):
        s = JAVA.read_text()
        for token in [
            'PACKAGE = "com.artcraft.vectorcraft"',
            'PACKAGE.equals(activity.getPackageName())',
            'target.getLongVersionCode() <= current.getLongVersionCode()',
            'sameSigningIdentity(current.signingInfo.getApkContentsSigners()',
            'MessageDigest.isEqual(',
            'if (written != c.bytes)',
            'sha256:[0-9a-fA-F]{64}',
            '"lib/arm64-v8a/libvectorcraft_android.so"',
            'trustedRedirect(current)',
            'canRequestPackageInstalls()',
            'PackageInstaller.SessionParams.MODE_FULL_INSTALL',
            'PackageInstaller.SessionParams.USER_ACTION_REQUIRED',
            'session.commit(sender.getIntentSender())',
            'STATUS_PENDING_USER_ACTION',
            'new Intent(activity, VectorCraftActivity.class)',
        ]:
            self.assertIn(token, s, token)
        self.assertNotIn('getExternalStoragePublicDirectory', s)
        self.assertNotIn('ACTION_VIEW, Uri.fromFile(', s)
        self.assertNotIn('PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED', s)

    def test_metadata_is_exact_immutable_release_asset(self):
        s = JAVA.read_text()
        for token in [
            'RELEASE_ASSET_BASE + "vectorcraft-v" + version + "/"',
            '"VectorCraft-v" + version + "-arm64-v8a.apk"',
            'expected.equals(url)',
            'digest.matches("sha256:',
            'MAX_BYTES = 400L * 1024L * 1024L',
        ]:
            self.assertIn(token, s)
        self.assertIn('volatile Candidate candidate', s)

    def test_explicit_user_action_and_event_isolation(self):
        s = PATCH.read_text()
        self.assertIn('"artcraft.vectorcraft.download_update_requested"', s)
        self.assertIn('if download_update_requested && !self.updates.checking', s)
        self.assertIn('self.bridge.download_verified_update(version)', s)
        self.assertIn('verifiedUpdater.start(version, updateIo);', s)
        self.assertIn('"android.permission.REQUEST_INSTALL_PACKAGES"', s)
        self.assertIn('about = once(about,', s)
        self.assertIn('downloadable && !checking && !downloading', s)
        self.assertIn('Test builds cannot replace the production app', JAVA.read_text())

    def test_staged_code_contract(self):
        staged = os.environ.get("VC_ANDROID5_STAGED")
        if not staged:
            self.skipTest("Generated code only exists after pinned upstream staging")
        root = Path(staged)
        java = root / "adapters/vectorcraft/java/com/artcraft/vectorcraft"
        activity = (java / "VectorCraftActivity.java").read_text()
        extras = (java / "VectorCraftExtras.java").read_text()
        installer = (java / "VectorCraftUpdateInstaller.java").read_text()
        rust = (root / "adapters/vectorcraft/src/lib.rs").read_text()
        about = (root / "source/vectorcraft/crates/ui-egui/src/dialogs/about.rs").read_text()
        manifest = (root / "adapters/vectorcraft/Cargo.toml").read_text()
        for token in ('verifiedUpdater.remember(latest, latestAssetUrl, latestDigest, latestAssetBytes)',
                      'result.put("downloadable", newer && verifiedUpdater.canDownload(latest))',
                      'void downloadUpdate(String version)', 'void updateInstallStatus(Intent intent)'):
            self.assertIn(token, extras)
        self.assertIn('vcDownloadUpdate(String version)', activity)
        self.assertIn('extras.updateInstallStatus(intent);', activity)
        self.assertIn('extras.updateInstallStatus(getIntent());', activity)
        self.assertIn('has_android_undo_chord(', rust)
        self.assertIn('fn download_verified_update(&self, version: &str)', rust)
        self.assertIn('self.updates.downloading', rust)
        self.assertIn('Download & Install VectorCraft', about)
        self.assertIn('REQUEST_INSTALL_PACKAGES', manifest)
        self.assertIn('sameSigningIdentity(', installer)

if __name__ == "__main__":
    unittest.main()
