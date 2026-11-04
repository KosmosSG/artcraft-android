"""VectorCraft-specific source guards: approved Android behavior, AndroidX splash,
persistent BFS font scanning, updater, keyboard and test-only signing.
"""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from patch_compact_apk_v020 import APPCOMPAT_THEME, patch_native_theme

ROOT=Path(__file__).resolve().parents[2]

class VectorCraftAndroid4Guards(unittest.TestCase):
    def test_androidx_splash_stays_until_pixelcopy_confirms_native_surface(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        theme=(ROOT/"tools/vectorcraft/patch_compact_apk_v020.py").read_text()
        for marker in (
            "import androidx.core.splashscreen.SplashScreen",
            "SplashScreen.installSplashScreen(this)",
            "setKeepOnScreenCondition(() -> !nativeEditorReady)",
            "PixelCopy.request(surface, pixels",
            "probeFirstPresentedFrame();",
            "nativeEditorReady = true",
            "showStartupCover();",
        ):
            self.assertIn(marker,java)
        for marker in ("windowSplashScreenBackground", "windowSplashScreenAnimatedIcon",
                       "postSplashScreenTheme", "core-splashscreen:1.0.1"):
            self.assertIn(marker,theme)

    def test_splash_resources_well_formed_and_switch_to_post_theme(self):
        base='<resources>\n    '+APPCOMPAT_THEME+'\n<item name="android:windowBackground">@android:color/black</item>\n    </style>\n</resources>'
        xml=patch_native_theme(base)
        ET.fromstring(xml)
        self.assertIn('<item name="windowSplashScreenBackground">#2d0000</item>',xml)
        self.assertIn('<item name="windowSplashScreenAnimatedIcon">@mipmap/ic_launcher</item>',xml)
        self.assertIn('<item name="postSplashScreenTheme">@style/Theme.ArtcraftPost</item>',xml)
        self.assertIn('parent="android:style/Theme.Material.NoActionBar"',xml)
        self.assertNotIn(r'\\n',xml)

    def test_bfs_persistence_unknown_sizes_and_incremental_async_fonts(self):
        extras=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        shell=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in (
            "MAX_FONTS = 5000",
            "MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",
            "MAX_FONTS_PER_PASS = 128",
            "MAX_SCAN_BATCH_BYTES = 64L * 1024 * 1024",
            "class ScanProgress", "ArrayDeque<ScanEntry>",
            "saveScanState(p)", "loadScanState(treeUri)",
            'report(id, "font_folder", "progress"',
            "scanFontFolder(id, treeUri);",
            "entry.reportedSize <= 0",
            "p.queue.addFirst(entry);",
            "addedThisPass",
        ):
            self.assertIn(marker,extras)
        self.assertIn('Some("progress")',shell)
        self.assertIn("return Some(added > 0);",shell)
        self.assertIn('name("vectorcraft-font-index"',shell)

    def test_preserve_android_features_and_disposable_signing(self):
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for marker in ("vcRequestFontImport", "vcRequestFontFolder", "vcRefreshFontFolder",
                       "vcCheckForUpdates", "vcPollUpdateResult", "vcOpenUpdatePage",
                       "applyImmersiveFullscreen"):
            self.assertIn(marker,java)
        for marker in ("ORIGINAL_CERT:", "Delete disposable builder signing materials",
                       "com.artcraft.vectorcraft.test", "0.21.0-android.5"):
            self.assertIn(marker,workflow)
        self.assertNotIn("gh release create",workflow)
        self.assertNotIn("softprops/action-gh-release",workflow)

if __name__ == "__main__":
    unittest.main()
