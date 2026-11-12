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
    def test_installer_uses_verified_private_bytes_and_confirmation(self):
        s=(ROOT/'templates/android/pdfcraft_update_java.txt').read_text()
        for token in ['pdfVerifiedSnapshot(downloaded, getCacheDir()', 'getPackageArchiveInfo(snapshot.getAbsolutePath()', 'new FileInputStream(snapshot)', 'USER_ACTION_REQUIRED', 'expectedVersion.equals(incoming.versionName)', 'before[0].toByteArray()', 'pdfInstallBusy.compareAndSet(false, true)', 'EXTRA_SESSION_ID', 'nonce.isEmpty()']:
            self.assertIn(token,s)
        self.assertNotIn('getUriForDownloadedFile',s)
        self.assertNotIn('!digest.isEmpty()',s)
if __name__=='__main__':unittest.main()
