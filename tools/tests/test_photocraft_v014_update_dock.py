"""Regression checks for PhotoCraft Android's LightCraft-style Updates and font pipeline."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUST = ROOT / "adapters/photocraft/src/lib.rs"
JAVA = ROOT / "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java"
POLICY = ROOT / "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftUpdatePolicy.java"
MENU = ROOT / "tools/photocraft_v014_menu_port.py"


class AndroidPhotoCraftUpdatesTests(unittest.TestCase):
    def test_lightcraft_style_updates_are_native_and_preserve_editor_space(self):
        rust, java = RUST.read_text(), JAVA.read_text()
        self.assertNotIn('egui::Panel::bottom("photocraft.android.update_status")', rust)
        self.assertIn('self.bridge.native_ui_call("settings")', rust)
        for marker in ("About PhotoCraft — Updates", "Installed Version:",
                       "Check for Updates", "Stable Releases Only",
                       "Stable + Preview Releases", "Check for updates at startup",
                       "Open Official GitHub Release", "pcRenderUpdateResult(result)",
                       "pcUpdateReleaseUrl = trusted ? url : null"):
            with self.subTest(marker=marker):
                self.assertIn(marker, java)

    def test_no_false_older_release_update_for_candidate(self):
        java, policy = JAVA.read_text(), POLICY.read_text()
        self.assertIn("PhotoCraftUpdatePolicy.compareVersions(latestVersion, installedVersion) > 0", java)
        self.assertIn("PhotoCraftUpdatePolicy.isNewer(latestCode, installedCode)", java)
        self.assertIn("static int compareVersions(String candidate, String installed)", policy)
        self.assertIn("candidateCode > installedCode", policy)
        self.assertIn('getBoolean("include_preview_releases", false)', java)
        self.assertNotIn("ACTION_INSTALL_PACKAGE", java)

    def test_font_import_persists_and_detected_catalog_is_visible(self):
        rust, java, menu = RUST.read_text(), JAVA.read_text(), MENU.read_text()
        for marker in ("fonts.register_font_data(bytes)", "engine.fonts.families()",
                       "artcraft.font_catalog", "pcShowFontCatalog",
                       "imported-{unique}-{id}", "self.picker.poll(&self.bridge, ctx)",
                       "picker.launch_shared_fonts(&bridge, true)"):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)
        self.assertIn("public void pcShowFontCatalog(String report)", java)
        self.assertIn("Detected Fonts…", menu)
        self.assertNotIn('dir.join(format!("imported-{id}.', rust)

    def test_progress_timeout_preserves_original_updater_and_android_features(self):
        rust = RUST.read_text()
        for marker in (
            "self.updates.started_at = Some(std::time::Instant::now());",
            "std::time::Duration::from_secs(30)",
            "self.updates.started_at = None;",
            "ctx.request_repaint_after(std::time::Duration::from_millis(250))",
            "https://github.com/KosmosSG/artcraft-android/releases/tag/photocraft-v",
            "self.shortcut_pad.show(", "artcraft.custom_fonts_visible",
            "artcraft.shared_fonts_select", "artcraft.shared_fonts_refresh",
            "artcraft.update_settings", "app_bridge.startup_update_enabled()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rust)


if __name__ == "__main__":
    unittest.main()
