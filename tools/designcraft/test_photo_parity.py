"""PhotoCraft-parity safety tests for the pinned DesignCraft Android candidate."""
import tempfile
from pathlib import Path
import unittest

from menu_overlay import apply


class DesignCraftAndroidParity(unittest.TestCase):
    def test_menu_overlay_is_pinned_and_fail_closed(self):
        pinned = Path("builder/source/designcraft/crates/ui-egui/src/menus.rs")
        self.assertTrue(pinned.is_file(), "Exact pinned upstream menus.rs checkout is required")
        with tempfile.TemporaryDirectory() as temp:
            edited = Path(temp) / "menus.rs"
            edited.write_bytes(pinned.read_bytes())
            original = edited.read_text()
            apply(edited)
            after = edited.read_text()
            self.assertNotEqual(original, after)
            self.assertIn('artcraft_take_android_actions()', after)
            self.assertIn('"Type" => &["app.artcraftImportFont"', after)
            self.assertIn('"Help" => &["help.artcraftCheckUpdates"', after)
            self.assertIn('"Window" => &["window.artcraftShortcutPad"', after)
            self.assertIn('entries.extend(ids.iter().map(|id| cmd_item(id, Value::Null)))', after)
            self.assertIn('entries.push(Item::Sep)', after)
            self.assertNotIn('entries.splice(0..0, android)', after)
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

    def test_android_font_cache_is_writable_and_scanned_after_import(self):
        from prepare_builder import patch_android_font_paths
        # Assert against the exact pinned builder file, not an unused suite copy.
        upstream = Path("builder/templates/android/system_fonts.rs").read_text()
        staged = patch_android_font_paths(upstream)
        self.assertIn('std::fs::read_link(&link)', staged)
        self.assertIn('std::fs::remove_file(&link)', staged)
        self.assertIn('std::fs::create_dir_all(&link)', staged)
        self.assertIn('link.join("android-system")', staged)
        self.assertIn('std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));', staged)
        self.assertNotIn('std::env::set_var("XDG_DATA_HOME", &base);', staged)
        with self.assertRaises(ValueError):
            patch_android_font_paths(staged)

        rust = Path("tools/designcraft/support/tablet.rs").read_text()
        java = Path("tools/designcraft/support/font_methods.java").read_text()
        self.assertIn('join(".local/share/fonts/imported")', rust)
        self.assertIn('"home/.local/share/fonts/shared"', java)
        self.assertIn('app.run("font.reload"', rust)
        self.assertIn('dcRestoreSharedFontsOnStartup()', java)

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
