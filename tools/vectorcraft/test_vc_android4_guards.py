"""Guard VectorCraft android.4 fixes before expensive ARM64 compilation.

The official v0.21.0 renderer is unchanged, and Android-only code must retain
all tested keyboard, pointer, icon, update and font features from android.3.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]


class VectorCraftAndroid4Guards(unittest.TestCase):
    def test_maintain_system_splash_until_native_editor_ready(self):
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        theme=(ROOT/"tools/vectorcraft/patch_compact_apk_v020.py").read_text()
        for marker in ("import android.window.SplashScreenView",
                       "getSplashScreen().setOnExitAnimationListener",
                       "nativeEditorReady = true",
                       "if (nativeEditorReady) finishSystemSplash();",
                       "finishSystemSplash();",
                       "splash.remove();",
                       "showStartupCover();"):
            self.assertIn(marker,java)
        self.assertIn("android:windowSplashScreenBackground",theme)
        self.assertIn("android:windowSplashScreenAnimatedIcon",theme)
        self.assertIn("#2d0000",theme)

    def test_auto_background_font_batches_and_safe_progress_updates(self):
        extras=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
        shell=(ROOT/"adapters/vectorcraft/src/lib.rs").read_text()
        for marker in ("MAX_FONTS = 5000",
                       "MAX_SCAN_BYTES = 4L * 1024 * 1024 * 1024",
                       "MAX_FONTS_PER_PASS = 128",
                       "MAX_SCAN_BATCH_BYTES = 64L * 1024 * 1024",
                       "TREE_SCAN_ADDED", "putInt(TREE_SCAN_ADDED",
                       "report(id, \"font_folder\", \"progress\"",
                       "scanFontFolder(id, treeUri);",
                       "bytes > 0 && bytes > MAX_SCAN_BATCH_BYTES - budget[0]",
                       "attempted--;",
                       "Existing fonts preserved"):
            self.assertIn(marker,extras)
        self.assertNotIn("if (bytes <= 0",extras)
        self.assertIn('Some("progress")',shell)
        self.assertIn("return Some(false);",shell)
        self.assertIn('name("vectorcraft-font-index"',shell)

    def test_stable_features_and_disposable_signing_retained(self):
        workflow=(ROOT/".github/workflows/vectorcraft-v021-test-apk.yml").read_text()
        java=(ROOT/"adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        for marker in ("vcRequestFontImport", "vcRequestFontFolder",
                       "vcRefreshFontFolder", "vcCheckForUpdates",
                       "vcPollUpdateResult", "vcOpenUpdatePage",
                       "applyImmersiveFullscreen"):
            self.assertIn(marker,java)
        for marker in ("ORIGINAL_CERT:", "Delete disposable builder signing materials",
                       "com.artcraft.vectorcraft.test",
                       "0.21.0-android.4"):
            self.assertIn(marker,workflow)
        self.assertNotIn("gh release create",workflow)
        self.assertNotIn("softprops/action-gh-release",workflow)


if __name__=="__main__":
    unittest.main()
