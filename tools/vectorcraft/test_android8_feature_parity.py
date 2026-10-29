"""Regression rules: keep exactly released .8 font/update UI and owner artwork;
add ONLY the already device-verified .9 physical-keyboard integration.
"""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
read=lambda name: (ROOT / name).read_text(encoding="utf-8")


class VectorCraftParity(unittest.TestCase):
    def test_menu_is_original_android8_bridge(self):
        menu = ROOT / "tools/vectorcraft/patch_android_menus.py"
        data = menu.read_bytes()
        self.assertEqual(hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest(),
                         "b29dbbfc63427487b7bd52fe655c91af952dc768",
                         "Do not change the reviewed .8 Android Type/Help/Window menu adapter")
        src = menu.read_text(encoding="utf-8")
        for symbol in ("android.vectorcraft.fontImport", "android.vectorcraft.fontFolder",
                       "android.vectorcraft.fontRefresh", "android.vectorcraft.updates",
                       "android.vectorcraft.startupUpdates",
                       "Import Font (.ttf / .otf)", "Check for VectorCraft Updates",
                       "Check for Updates at Startup", "Refresh Shared Fonts"):
            self.assertIn(symbol, src)

    def test_production_android8_fonts_feedback_and_updater_are_preserved(self):
        shell = read("adapters/vectorcraft/src/lib.rs")
        extras = read("adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java")
        for marker in ("fn request_font_import(&self", "fn request_font_folder(&self",
                       "fn check_for_updates(&self", "vcRequestFontImport",
                       "vcRequestFontFolder", "vcRefreshFontFolder", "vcCheckForUpdates",
                       "FontUiState", "import_status", "shared_status", "poll_update_result()",
                       "text.rescanFonts", "persist_write(",
                       "Startup", "ARTCRAFT_VECTORCRAFT_SAF_BRIDGE_V1"):
            with self.subTest(marker=marker):
                if marker == "Startup":
                    self.assertIn("startup_updates", shell)
                else:
                    self.assertIn(marker, shell)
        for marker in ("requestFontImport", "requestFontFolder", "refreshFontFolder",
                       "checkForUpdates", "pollUpdate"):
            self.assertIn(marker, extras)

    def test_original_08_icon_assets_and_versions_are_immutable(self):
        approved = ROOT / "tools/approved-branding/assets/manifest.json"
        manifest=json.loads(approved.read_text())
        self.assertEqual(manifest["version_name"], "0.14.0-android.8")
        self.assertEqual(manifest["version_code"], 16780808)
        self.assertEqual(manifest["source_sha256"],
                         "07eed59ba0564ebcc199004248469d5a0f663340e0a46843552ca7261ce0892f")
        for p,h in manifest["resources"].items():
            self.assertEqual(hashlib.sha256((approved.parent/p).read_bytes()).hexdigest(),h)
        restore = read("tools/vectorcraft/restore_vectorcraft_08_branding.py")
        self.assertIn('"install"', restore)
        self.assertIn('VERSION = "0.14.0-android.12"', restore)
        self.assertIn("installed[", restore)

    def test_keyboard_shortcuts_still_recover_after_escape(self):
        shell = read("adapters/vectorcraft/src/lib.rs")
        mods = read("adapters/vectorcraft/src/android_modifiers.rs")
        for key in ("CanvasHardwareCommand::ExitType", "CanvasHardwareCommand::PreserveContextBar",
                    "CanvasHardwareCommand::Selection", "CanvasHardwareCommand::Type",
                    "CanvasHardwareCommand::Pen", "self.bridge.end_type_editing()",
                    "memory.surrender_focus(id)"):
            self.assertIn(key, shell)
        self.assertNotIn("self.inner.ui.task_bar = false;", shell)
        for test in ("type_shortcut_returns_after_escape_exits_editor",
                     "escape_preserves_context_bar_and_tool_shortcuts",
                     "direct_tool_dispatch_consumes_only_matching_letter_events"):
            self.assertIn(test, mods)


if __name__ == "__main__":
    unittest.main()
