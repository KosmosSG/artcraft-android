"""Exercise the exact private-path predicate with canonical traversal/symlink paths."""
from pathlib import Path
import re, shutil, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]
class IncomingPaths(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required in CI')
    def test_private_root_children_aliases_and_public_prefix_sibling(self):
        source = (ROOT/'templates/android/pdfcraft_mobile_java.txt').read_text()
        helper = re.search(r'private static boolean pdfPathWithin\(.*?\n}', source, re.S).group()
        harness = '''import java.io.*; import java.nio.file.*;
public class PathCheck {
HELPER
public static void main(String[] args) throws Exception {
 Path root=Files.createTempDirectory("pdf-path-test");
 Path privateDir=Files.createDirectory(root.resolve("private"));
 Path publicDir=Files.createDirectory(root.resolve("private-other"));
 Path secret=Files.write(privateDir.resolve("secret"),new byte[]{1});
 Path link=Files.createSymbolicLink(root.resolve("link"), privateDir);
 File data=privateDir.toFile().getCanonicalFile();
 for (Path candidate:new Path[]{privateDir, secret, link.resolve("secret"), publicDir.resolve("../private/secret")})
  if(!pdfPathWithin(candidate.toFile().getCanonicalFile(),data)) throw new AssertionError("private path accepted");
 if(pdfPathWithin(publicDir.resolve("doc.pdf").toFile().getCanonicalFile(),data)) throw new AssertionError("normal file rejected");
 Files.delete(link); Files.delete(secret); Files.delete(privateDir); Files.delete(publicDir); Files.delete(root);
}}
'''.replace('HELPER', helper)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'PathCheck.java'; p.write_text(harness)
            subprocess.run(['javac',str(p)],check=True)
            subprocess.run(['java','-cp',td,'PathCheck'],check=True)
