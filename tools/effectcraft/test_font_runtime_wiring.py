"""Static wiring guards for the Android font bridge.

These deliberately cannot substitute for an ARM64 compile or MagicPad font test.
They catch the regression where the picker stores TTF/OTF files but the runtime
never advertises a successfully registered family in Character/Properties.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).parent


class FontRuntimeWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = (ROOT / "FontsBridge.java.inc").read_text()
        cls.rust = (ROOT / "android_updater.rs").read_text()
        cls.integration = (ROOT / "integrate_updater.py").read_text()

    def test_manual_import_is_distinguished_from_background_restore(self):
        self.assertIn('ecCopyFont(uri, name, new long[]{0}, true);', self.java)
        self.assertIn('name, budget, false);', self.java)
        self.assertIn('ecFontPaths.offer((manual ? "manual|" : "") + target.getAbsolutePath());', self.java)
        self.assertIn('getStringSet("manual_imports"', self.java)
        self.assertIn('putStringSet("manual_imports", remembered)', self.java)
        self.assertIn('ecFontPaths.offer(font.getAbsolutePath());', self.java)
        self.assertIn('path.strip_prefix("manual|")', self.rust)

    def test_rust_registers_faces_before_success_feedback(self):
        self.assertIn('effectcraft_text::fonts::android_add_font_file(&file)', self.rust)
        self.assertIn('effectcraft_text::fonts::face(faces[0]).info.family.clone()', self.rust)
        self.assertIn('Font ready: {family}', self.rust)
        self.assertIn('Ok(status) if manual', self.rust)
        self.assertIn('Font imported successfully.', self.rust)
        self.assertIn('Font engine could not read any faces', self.rust)
        self.assertIn('std::panic::catch_unwind', self.rust)

    def test_only_canonical_private_ttf_or_otf_files_are_loaded(self):
        self.assertIn('std::fs::canonicalize(root)', self.rust)
        self.assertIn('std::fs::canonicalize(&path)', self.rust)
        self.assertIn('file.parent() == Some(root.as_path())', self.rust)
        self.assertIn('eq_ignore_ascii_case("ttf")', self.rust)
        self.assertIn('eq_ignore_ascii_case("otf")', self.rust)

    def test_crash_loop_guard_and_explicit_refresh(self):
        start = self.java.split("    public void ecInitialize() {", 1)[1].split("    public void ecImportFont()", 1)[0]
        self.assertNotIn("ecRefreshSharedFonts(false)", start)
        self.assertNotIn("ecFontDir().listFiles()", start)
        self.assertIn("manual_imports", start)
        tree = self.java.split("if (requestCode == EC_FONT_PICK)", 1)[1].split("private void ecCopyFont", 1)[0]
        self.assertIn("Tap Refresh Shared Fonts", tree)
        self.assertNotIn("ecRefreshSharedFonts(true)", tree)
        refresh = self.java.split("    public void ecRefreshFonts()", 1)[1]
        self.assertIn("EC_SCAN_FILES = 5000", self.java)
        self.assertIn("EC_SCAN_MAX = 4L * 1024 * 1024 * 1024", self.java)
        self.assertIn("ecFontQueueRoom()", refresh)
        self.assertIn("Low storage; font scan stopped safely", self.java)
        self.assertNotIn("remove_file(&file)", self.rust)

    def test_jni_and_font_menu_remain_connected(self):
        for symbol in ('ecPollFontPath', 'ecInitialize', 'ecImportFont', 'ecSelectSharedFonts', 'ecRefreshFonts'):
            self.assertIn(symbol, self.java)
            self.assertIn(symbol, self.rust)
        self.assertIn('tools/effectcraft/android_updater.rs', self.integration)
        self.assertIn('FontsBridge.java.inc', self.integration)
        self.assertIn('artcraft.effectcraft.import_font', self.integration)


if __name__ == "__main__":
    unittest.main()
