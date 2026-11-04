"""Regression checks for the Android-only top-left Vc menu and launch overlay.

Runs before the expensive ARM64 native build, with no device, network or keys.
"""
from pathlib import Path
import unittest

from patch_android_menus_v020 import (
    add_vc_menu, VC_APP_MENU_BOUNDARY, VC_APP_MENU_WITH_ANDROID,
)

ROOT = Path(__file__).resolve().parents[2]


class VcMenuAndStartupChecks(unittest.TestCase):
    def test_vc_menu_is_first_visible_android_menu(self):
        source = "before\n" + VC_APP_MENU_BOUNDARY + "\nafter\n"
        updated = add_vc_menu(source)
        self.assertIn(VC_APP_MENU_WITH_ANDROID, updated)
        self.assertLess(updated.index('            "Vc",'), updated.index('            "File",'))
        self.assertIn('#[cfg(target_os = "android")]', updated)
        self.assertIn('vec![c("About VectorCraft", "help.about"), c("Join Our Discord", "help.discord")]', updated)
        for command in (
            "android.vectorcraft.fontImport",
            "android.vectorcraft.fontFolder",
            "android.vectorcraft.fontRefresh",
            "android.vectorcraft.updates",
            "android.vectorcraft.startupUpdates",
        ):
            self.assertIn(command, updated)
        # Type and Help legacy entries are never removed by this insertion.
        self.assertEqual(source.split(VC_APP_MENU_BOUNDARY)[0],
                         updated.split(VC_APP_MENU_WITH_ANDROID)[0])

    def test_unknown_or_repeated_tree_fails_closed(self):
        with self.assertRaises(RuntimeError):
            add_vc_menu("unreviewed upstream tree")
        with self.assertRaises(RuntimeError):
            add_vc_menu(VC_APP_MENU_BOUNDARY + VC_APP_MENU_BOUNDARY)

    def test_native_cover_has_a_timeout_and_matching_jni_hook(self):
        activity = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        rust = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        self.assertIn("showStartupCover();", activity)
        self.assertIn("R.mipmap.ic_launcher", activity)
        self.assertIn("public void vcNativeUiReady()", activity)
        self.assertIn("cover.postDelayed(this::dismissStartupCover, 15000)", activity)
        self.assertIn('jni_str!("vcNativeUiReady")', rust)
        self.assertIn("self.bridge.notify_native_ui_ready()", rust)
        self.assertIn("startup_updates.enabled", rust)
        self.assertIn("if startup_updates && app_bridge.check_for_updates().is_ok()", rust)


if __name__ == "__main__":
    unittest.main()
