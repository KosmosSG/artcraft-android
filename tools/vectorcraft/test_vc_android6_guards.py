"""Cheap regression gates for VectorCraft Android.6 owner-device issues."""
from pathlib import Path
import unittest
from patch_smooth_menu_scroll_v021 import patch_source, ORIGINAL

ROOT=Path(__file__).resolve().parents[2]


class VectorCraftAndroid6Guards(unittest.TestCase):
    def test_trackpad_menu_patch_does_not_affect_upstream_desktop(self):
        untouched="// existing egui Vulkan-menu widgets\n"
        updated=patch_source(untouched+ORIGINAL)
        self.assertEqual(updated.split("        let area =")[0],untouched)
        for marker in (
            "#[cfg(target_os = \"android\")]",
            '.id_salt("vectorcraft-android-smooth-menu")',
            ".wheel_scroll_multiplier(egui::vec2(1.0, 0.78))",
            "input.is_scrolling()",
            "request_repaint_after(std::time::Duration::from_millis(16))",
            "area.show(ui, add_contents).inner"
        ):
            self.assertIn(marker,updated)
        with self.assertRaises(ValueError): patch_source(updated)
        with self.assertRaises(ValueError): patch_source(untouched+"unreviewed upstream scroll area")

    def test_splash_waits_for_actual_editor_gpu_details(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for marker in (
            "import android.graphics.drawable.ColorDrawable;",
            "private int verifiedNativeFrames;",
            "Bitmap.createBitmap(24, 16, Bitmap.Config.ARGB_8888)",
            "verifiedNativeFrames = meaningfulFrame ? verifiedNativeFrames + 1 : 0;",
            "verifiedNativeFrames >= 2",
            "bright >= 3 && dark >= 3",
            "setKeepOnScreenCondition(() -> !nativeEditorReady)",
            "getWindow().setBackgroundDrawable(new ColorDrawable(Color.rgb(45, 0, 0)))",
            "No rendered frame after 20s",
            "PixelCopy.request(surface, pixels",
        ):
            self.assertIn(marker,java)

    def test_font_scan_and_original_working_features_untouched(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        adapter=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in (
            "MAX_FONTS = 5000", "MAX_FONTS_PER_PASS = 128",
            "MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",
            "class ScanProgress", "loadScanState(treeUri)",
            "saveScanState(p)", "scanFontFolder(id, treeUri)",
            'report(id, "font_folder", "progress"',
        ):
            self.assertIn(marker,java)
        activity=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for marker in ("vcRequestFontImport", "vcRequestFontFolder",
                       "vcCheckForUpdates", "vcPollUpdateResult"):
            self.assertIn(marker,activity)
        for marker in ("font_reindex_pending", "notify_native_ui_ready",
                       "classify_android_precision_scroll", "startup_updates"):
            self.assertIn(marker,adapter)

    def test_only_test_apk_permitted(self):
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        for marker in ("VERSION_NAME: 0.21.0-android.6",
                       "VERSION_CODE: '16783366'",
                       "patch_smooth_menu_scroll_v021.py builder",
                       "com.artcraft.vectorcraft.test",
                       "Delete disposable builder signing materials"):
            self.assertIn(marker,workflow)
        self.assertNotIn("gh release create",workflow)
        self.assertNotIn("softprops/action-gh-release",workflow)


if __name__=="__main__": unittest.main()
