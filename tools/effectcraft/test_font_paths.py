"""Check DesignCraft's released migration against EffectCraft's real builder template."""
import unittest
from pathlib import Path
from font_paths import patch_android_font_paths

class FontPaths(unittest.TestCase):
    def test_real_template_and_repeat_guard(self):
        root = Path(__file__).resolve().parents[2]
        original = (root / 'templates/android/system_fonts.rs').read_text()
        staged = patch_android_font_paths(original)
        self.assertIn('std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));', staged)
        self.assertIn('std::fs::read_link(&link).ok().as_deref()', staged)
        self.assertIn('== Some(std::path::Path::new("/system/fonts"))', staged)
        self.assertIn('link.join("android-system")', staged)
        self.assertNotIn('std::env::set_var("XDG_DATA_HOME", &base);', staged)
        with self.assertRaises(ValueError): patch_android_font_paths(staged)
        # EffectCraft's existing importer registers directly, so keep its persistent location.
        java = (root / 'tools/effectcraft/FontsBridge.java.inc').read_text()
        rust = (root / 'tools/effectcraft/android_updater.rs').read_text()
        self.assertIn('new File(getFilesDir(), "custom-fonts")', java)
        self.assertIn('effectcraft_text::fonts::add_font_data(bytes)', rust)
        self.assertIn('Font ready:', rust)

    def test_drift_fails_closed(self):
        with self.assertRaises(ValueError): patch_android_font_paths('unexpected builder')
