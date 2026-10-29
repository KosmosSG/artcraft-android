"""Execute actual bridge copying methods on JVM; catalog parsing is tested in Rust CI."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent

class RecursiveFonts(unittest.TestCase):
    def test_scan_bounds_and_runtime_registration(self):
        java = (ROOT / 'FontsBridge.java.inc').read_text()
        rust = (ROOT / 'android_updater.rs').read_text()
        for token in ('64L * 1024 * 1024', '2L * 1024 * 1024 * 1024',
                      'EC_SCAN_FILES = 5000, EC_SCAN_FOLDERS = 5000',
                      'pending.addLast(id)', 'seen.add(parent)',
                      'getPersistedUriPermissions()', 'summary|',
                      '"/system/fonts"', '"/product/fonts"'):
            self.assertIn(token, java)
        self.assertIn('android_add_font_file(&file)', rust)
        self.assertIn('registered families', rust)
        self.assertIn('if !system { let _ = std::fs::remove_file', rust)

    @unittest.skipUnless(shutil.which('javac'), 'JDK required; executed in private CI')
    def test_real_copy_deduplicates_collections_and_preserves_on_failure(self):
        source = (ROOT / 'FontsBridge.java.inc').read_text()
        helpers = source[source.index('    private static final long EC_FONT_MAX'):source.index('    private static final int EC_FONT_PICK')]
        method = source[source.index('    private void ecCopyFont('):source.index('    public void ecRefreshFonts()')]
        harness = r'''
import java.io.*;
import java.util.*;
public class FontCopyTest {
  static class Uri { byte[] data; Uri(byte[] b) { data=b; } }
  static class Resolver { InputStream openInputStream(Uri uri) { return new ByteArrayInputStream(uri.data); } }
  final File dir;
  FontCopyTest(File d) { dir=d; }
  File ecFontDir() { return dir; }
  Resolver getContentResolver() { return new Resolver(); }
  java.util.concurrent.ConcurrentLinkedQueue<String> ecFontPaths = new java.util.concurrent.ConcurrentLinkedQueue<>();
  static void check(boolean ok) { if (!ok) throw new AssertionError(); }
  public static void main(String[] args) throws Exception {
    FontCopyTest t = new FontCopyTest(new File(args[0]));
    byte[] font = new byte[32]; font[0]='t'; font[1]='t'; font[2]='c'; font[3]='f';
    t.ecCopyFont(new Uri(font), "COLLECTION.TTC", new long[]{0}, true);
    t.ecCopyFont(new Uri(font), "COLLECTION.TTC", new long[]{0}, true);
    check(t.dir.list().length == 1);
    check(t.dir.list()[0].endsWith(".ttc"));
    check(t.ecFontPaths.poll().startsWith("manual|"));
    try { t.ecCopyFont(new Uri(font), "bad.exe", new long[]{0}, true); throw new AssertionError(); }
    catch (IOException expected) { }
    try { t.ecCopyFont(new Uri(font), "test.ttc", new long[]{EC_SCAN_MAX}, true); throw new AssertionError(); }
    catch (IOException expected) { }
    check(t.dir.list().length == 1); // previous cached font survived, no pending file
    byte[] huge = new byte[(int)EC_FONT_MAX + 1]; huge[1]=1;
    try { t.ecCopyFont(new Uri(huge), "huge.ttf", new long[]{0}, true); throw new AssertionError(); }
    catch (IOException expected) { }
    check(t.dir.list().length == 1);
    check(ecFontName("a.OTF") && ecFontName("a.ttf") && ecFontName("a.TTC"));
    check(!ecFontName("a.ttf.exe"));
  }
'''
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'FontCopyTest.java').write_text(harness + helpers + method + '\n}')
            subprocess.run(['javac', str(p / 'FontCopyTest.java')], check=True, capture_output=True)
            subprocess.run(['java', '-cp', folder, 'FontCopyTest', str(p / 'fonts')], check=True, capture_output=True)

if __name__ == '__main__':
    unittest.main()
