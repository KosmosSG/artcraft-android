"""Keep compiled FilmCraft APK verification aligned with the one Help menu action.

Offline source-level contract check. The APK audit itself independently verifies
these exact commands in the compiled ARM64 library and Java DEX.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_menu_patch as menus
import header_patch as header
import verify_android_features_apk as apk_audit


class NativeUpdateMenuContractTests(unittest.TestCase):
    def test_single_upstream_help_entry_and_android_action(self):
        self.assertEqual(menus.UPSTREAM_UPDATE_ENTRY.count('"Check for Updates…"'), 1)
        source = (
            menus.UPSTREAM_UPDATE_ENTRY + "\n" + menus.COMMAND_ANCHOR +
            "\n" + menus.INVOKE_ANCHOR + "\n" + menus.MENU_BAR_ANCHOR + "\n"
        )
        staged = menus.patch(source)
        self.assertEqual(staged.count('"Check for Updates…"'), 1)
        self.assertEqual(staged.count('uic!("app.checkForUpdates"'), 1)
        self.assertIn('"app.checkForUpdates" => Some(4),', staged)
        self.assertNotIn('uic!("android.filmcraft.checkUpdates"', staged)

    def test_icon_popup_preserves_commands_and_removes_duplicates_from_file_help(self):
        source = menus.UPSTREAM_UPDATE_ENTRY + "\n" + menus.COMMAND_ANCHOR + "\n" + menus.INVOKE_ANCHOR + "\n" + menus.MENU_BAR_ANCHOR + "\n"
        staged = menus.patch(source)
        for command in (
            "android.filmcraft.importFont", "android.filmcraft.sharedFonts",
            "android.filmcraft.refreshFonts", "app.checkForUpdates",
            "android.filmcraft.startupUpdates"
        ):
            self.assertIn('"' + command + '"', staged)
            self.assertIn('"' + command + '"', menus.ANDROID_ICON_MENU_FILTER)
        for label in ("Import Font…", "Shared Font Folder…", "Refresh Imported Fonts",
                      "Check for Updates…", "Check for Updates at Startup"):
            self.assertIn(label, header.ANDROID_HOME)
        self.assertIn("Mode::Import", header.ANDROID_HOME)
        self.assertIn("android_approved_brand::paint", header.ANDROID_HOME)
        self.assertIn("widgets.hovered.weak_bg_fill", header.MENU_STYLE)
        header.self_test()

    def test_compiled_audit_requires_upstream_update_id_not_obsolete_id(self):
        self.assertIn(b"app.checkForUpdates", apk_audit.NATIVE_COMMANDS)
        self.assertNotIn(b"android.filmcraft.checkUpdates", apk_audit.NATIVE_COMMANDS)
        self.assertIn(b"fcCheckForUpdates", apk_audit.JAVA_METHODS)
        self.assertEqual(apk_audit.NATIVE_COMMANDS.count(b"app.checkForUpdates"), 1)

    def test_upstream_menu_drift_and_duplicate_are_fail_closed(self):
        stub = (
            menus.UPSTREAM_UPDATE_ENTRY + "\n" + menus.COMMAND_ANCHOR +
            "\n" + menus.INVOKE_ANCHOR + "\n" + menus.MENU_BAR_ANCHOR + "\n"
        )
        for bad in (
            stub.replace(menus.UPSTREAM_UPDATE_ENTRY, ""),
            stub.replace(menus.UPSTREAM_UPDATE_ENTRY, menus.UPSTREAM_UPDATE_ENTRY * 2),
        ):
            with self.subTest(bad=bad[:90]), self.assertRaises(RuntimeError):
                menus.patch(bad)


if __name__ == "__main__":
    unittest.main()
