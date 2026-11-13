"""Runs the actual snapshot helper on a host JVM; Android installer gates are checked separately."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[2]
class SnapshotTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required; mandatory in CI')
    def test_exact_bytes_tamper_missing_digest_size_limit_and_cleanup(self):
        helper=(ROOT/'templates/android/pdfcraft_update_snapshot.java.txt').read_text()
        harness='''import java.io.*; import java.nio.file.*;
public class SnapshotTest {
HELPER
 public static void main(String[] args) throws Exception {
  File dir=Files.createTempDirectory("snapshot-test").toFile();
  File source=new File(dir,"source.apk"); Files.write(source.toPath(),new byte[]{1,2,3});
  String hash="sha256:039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81";
  File good=pdfVerifiedSnapshot(source,dir,hash,3);
  Files.write(source.toPath(),new byte[]{9,9,9});
  if (!java.util.Arrays.equals(Files.readAllBytes(good.toPath()),new byte[]{1,2,3})) throw new AssertionError("mutable snapshot");
  good.delete();
  for (String digest:new String[]{hash,"","sha256:bad"}) {
   try { pdfVerifiedSnapshot(source,dir,digest,3); throw new AssertionError("accepted bad digest"); }
   catch (SecurityException expected) {}
  }
  Files.write(source.toPath(),new byte[]{1,2,3});
  try {pdfVerifiedSnapshot(source,dir,hash,2);throw new AssertionError("oversize accepted");}catch(SecurityException expected){}
  if(dir.list().length!=1)throw new AssertionError("temporary leak");
  source.delete();dir.delete();System.out.println("PASS: snapshot tamper, missing digest, size bound and cleanup");
 }
}'''.replace('HELPER',helper)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'SnapshotTest.java';p.write_text(harness)
            subprocess.run(['javac',str(p)],check=True)
            subprocess.run(['java','-cp',td,'SnapshotTest'],check=True)
    def test_verified_download_updater_has_no_package_installer(self):
        s=(ROOT/'templates/android/pdfcraft_update_java.txt').read_text()
        self.assertIn('pdfDownloadStatus()',s)
        self.assertIn('pdfDownloadUpdate(String url, String sha256Digest)',s)
        self.assertIn('pdfInstallDownloadedUpdate()',s)
        self.assertIn('pdfHandleInstallResult(Intent intent)',s)
        self.assertIn('In-app APK installation is disabled.',s)
        self.assertIn('pdfApprovedAssetName',s)
        self.assertIn('pdfExportDownloadedUpdate',s)
        self.assertIn('pdfHandleExportResult',s)
        self.assertIn('MessageDigest.getInstance("SHA-256")',s)
        for token in ('PackageInstaller','getPackageInstaller(', 'canRequestPackageInstalls()',
                      'ACTION_MANAGE_UNKNOWN_APP_SOURCES','DownloadManager',
                      'getUriForDownloadedFile', 'USER_ACTION_REQUIRED'):
            self.assertNotIn(token,s)
if __name__=='__main__':unittest.main()
