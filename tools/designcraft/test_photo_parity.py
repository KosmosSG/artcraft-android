"""PhotoCraft-parity safety tests for the pinned DesignCraft Android candidate."""
import tempfile
import shutil
from pathlib import Path
import unittest

from menu_overlay import apply


class DesignCraftAndroidParity(unittest.TestCase):
    def test_menu_overlay_is_pinned_and_fail_closed(self):
        menus_root = Path("builder/source/designcraft/crates/ui-egui/src")
        pinned = menus_root / "menus.rs"
        self.assertTrue(pinned.is_file(), "Exact pinned upstream menus.rs checkout is required")
        with tempfile.TemporaryDirectory() as temp:
            if (menus_root / "menus/ui_commands.rs").is_file():
                edited = Path(temp) / "menus"
                shutil.copytree(menus_root / "menus", edited)
                shutil.copyfile(pinned, Path(temp) / "menus.rs")
                def contents():
                    return "\\n".join(p.read_text() for p in [Path(temp) / "menus.rs", *sorted(edited.glob("*.rs"))])
            else:
                edited = Path(temp) / "menus.rs"
                edited.write_bytes(pinned.read_bytes())
                def contents():
                    return edited.read_text()
            original = contents()
            apply(edited)
            after = contents()
            self.assertNotEqual(original, after)
            self.assertIn('artcraft_take_android_actions()', after)
            self.assertIn('"Type" => &["app.artcraftImportFont"', after)
            self.assertIn('"Help" => &["help.artcraftCheckUpdates"', after)
            self.assertIn('"Window" => &["window.artcraftShortcutPad"', after)
            with self.assertRaises(ValueError):
                apply(edited)

    def test_font_cache_refresh_never_deletes_previous_good_file(self):
        java = Path("tools/designcraft/support/font_methods.java").read_text()
        self.assertIn('dcRestoreSharedFontsOnStartup()', java)
        self.assertIn('getPersistedUriPermissions()', java)
        self.assertIn('new File(cache, "font-" + hash + extension + ".pending")', java)
        self.assertIn('StandardCopyOption.ATOMIC_MOVE', java)
        self.assertIn('if (!validHeader)', java)
        self.assertNotIn('target.delete();', java)

    def test_updater_rejects_disposable_test_package(self):
        java = Path("tools/designcraft/support/update_methods.java").read_text()
        self.assertIn('if (!"com.artcraft.designcraft".equals(getPackageName()))', java)
        self.assertIn('dcChecking.compareAndSet(false, true)', java)
        self.assertIn('release.optBoolean("prerelease")', java)
        self.assertNotIn('ACTION_INSTALL_PACKAGE', java)

    def test_touch_pad_is_opt_in_persistent_and_text_safe(self):
        rust = Path("tools/designcraft/support/tablet.rs").read_text()
        self.assertIn('android-shortcuts-enabled', rust)
        self.assertIn('ctx().text_edit_focused()', rust)
        self.assertIn('min_size(egui::vec2(56.0, 44.0))', rust)
        self.assertIn('artcraft_take_android_actions()', rust)


if __name__ == "__main__":
    unittest.main()
