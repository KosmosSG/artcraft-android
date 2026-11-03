"""Compile-stage syntax guard for GridCraft's generated Java Activity fragment.

Runs with the stock Ubuntu JDK, without Android SDK, Gradle or an ARM64 build.
The Java compiler API parses only; unresolved Android platform symbols are not
an error until type checking, which is intentionally NOT invoked.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

JAVA = Path(__file__).resolve().parent / "android_addons" / "GridCraftJavaMethods.java.inc"
UPDATER = Path(__file__).resolve().parent / "android_addons" / "GridCraftSafeUpdater.java.inc"
PARSER = r"""
import com.sun.source.util.JavacTask;
import javax.tools.*;
import java.util.*;
public class GridCraftJavaParseOnly {
    public static void main(String[] args) throws Exception {
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) throw new IllegalStateException("JDK javac unavailable");
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        try (StandardJavaFileManager files = compiler.getStandardFileManager(diagnostics, null, null)) {
            Iterable<? extends JavaFileObject> sources = files.getJavaFileObjects(args[0]);
            JavacTask task = (JavacTask) compiler.getTask(null, files, diagnostics, List.of("-proc:none"), null, sources);
            task.parse(); // syntax ONLY; no Java/Android symbol resolution or compilation
        }
        long errorCount = 0;
        for (Diagnostic<? extends JavaFileObject> d : diagnostics.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR) {
                errorCount++;
                System.err.println("GridCraftActivity.java:" + d.getLineNumber() + ": " + d.getMessage(null));
            }
        }
        if (errorCount != 0) System.exit(1);
        System.out.println("PASS: GridCraft Java Activity fragment parses without syntax errors");
    }
}
"""


class GridCraftJavaSyntaxTests(unittest.TestCase):
    def test_no_escaped_literal_newline_can_comment_out_a_method(self):
        java = JAVA.read_text()
        self.assertNotIn("\\n", java,
                         "Literal backslash-n in Java injection comments out subsequent method headers")
        self.assertIn("private static final int GC_MAX_SHARED_FONTS = 5000;\n", java)
        self.assertIn("private static final int GC_MAX_SHARED_DIRS = 5000;\n", java)
        self.assertIn("private void gcScanShared(android.net.Uri tree) {\n", java)
        self.assertIn("    }\n\n    private static void gcDeleteTree", java)

    def test_download_and_install_has_candidate_and_signature_safety_checks(self):
        src = UPDATER.read_text()
        self.assertIn('getPackageName().endsWith(".candidate")', src)
        self.assertIn("getPackageArchiveInfo(", src)
        self.assertIn("getApkContentsSigners()", src)
        self.assertIn("gcDigestHex(sha.digest())", src)
        self.assertIn("android.content.Intent.ACTION_VIEW", src)
        self.assertIn("FLAG_GRANT_READ_URI_PERMISSION", src)
        self.assertNotIn("SessionParams", src)  # Never silent installation
        self.assertIn("512L * 1024 * 1024", src)

    def test_java_fragment_is_valid_java_syntax_before_full_android_build(self):
        java_bin, javac_bin = shutil.which("java"), shutil.which("javac")
        self.assertIsNotNone(java_bin, "JDK must be present for build-source preflight")
        self.assertIsNotNone(javac_bin, "JDK must be present for build-source preflight")
        with tempfile.TemporaryDirectory(prefix="gridcraft-java-syntax-") as tmp:
            folder = Path(tmp)
            activity = folder / "GridCraftActivity.java"
            activity.write_text("package com.artcraft.gridcraft.candidate;\n"
                                "public class GridCraftActivity {\n"
                                + JAVA.read_text() + "\n" + UPDATER.read_text() + "\n}\n")
            parser = folder / "GridCraftJavaParseOnly.java"
            parser.write_text(PARSER)
            compile = subprocess.run([javac_bin, "-d", tmp, str(parser)],
                                     capture_output=True, text=True, timeout=45)
            self.assertEqual(compile.returncode, 0, compile.stdout + compile.stderr)
            check = subprocess.run([java_bin, "-cp", tmp, "GridCraftJavaParseOnly", str(activity)],
                                   capture_output=True, text=True, timeout=45)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
