"""LightCraft's Android-only update controls must preserve the PhotoCraft parity contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class LightCraftUpdatesSourceContract(unittest.TestCase):
    def test_java_startup_preference_defaults_off_and_persists(self):
        java = (ROOT / "lightcraft_updates.java.inc").read_text()
        self.assertIn('getBoolean("check_at_startup", false)', java)
        self.assertIn('putBoolean("check_at_startup", enabled).apply()', java)
        self.assertIn("lcGetStartupUpdateCheck()", java)
        self.assertIn("lcSetStartupUpdateCheck(boolean enabled)", java)
        self.assertIn('setConnectTimeout(8000)', java)
        self.assertIn('setReadTimeout(8000)', java)

    def test_exact_lightcraft_release_scope(self):
        java = (ROOT / "lightcraft_updates.java.inc").read_text()
        self.assertIn('release.optBoolean("draft")', java)
        self.assertIn('release.optBoolean("prerelease")', java)
        self.assertIn("LightCraft-v", java)
        self.assertIn("LightCraft-", java)
        self.assertIn('"uploaded".equals(state)', java)
        self.assertIn('asset.optLong("size", 0L) > 0L', java)
        self.assertNotIn('name.contains("arm64")', java)
        self.assertIn('latestCode > installedCode', java)
        self.assertIn("https://api.github.com/repos/KosmosSG/artcraft-android/releases?", java)

    def test_rust_manual_and_startup_controls(self):
        rust = (ROOT / "lightcraft_updates.rs").read_text()
        self.assertIn('artcraft.lightcraft.check_updates_requested', rust)
        self.assertIn('artcraft.lightcraft.startup_updates_requested', rust)
        self.assertIn('lcGetStartupUpdateCheck', rust)
        self.assertIn('lcSetStartupUpdateCheck', rust)
        self.assertIn('JValue::Bool(enabled)', rust)
        self.assertNotIn('JValue::Bool(if enabled { 1 } else { 0 })', rust)
        self.assertIn('self.begin_check(app, true)', rust)
        self.assertIn('if was_background && state != "update_available"', rust)
        self.assertIn('Open GitHub Release', rust)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", rust)

    def test_help_menu_directly_below_about(self):
        integration = (ROOT / "apply_android_fixes.py").read_text()
        self.assertIn('("app.about", "About LightCraft"', integration)
        self.assertIn('"app.artcraftStartupUpdateSettings"', integration)
        self.assertIn('Help menu layout directly under About LightCraft', integration)
        self.assertIn('LightCraft Android Help command handler', integration)


if __name__ == "__main__":
    unittest.main()
