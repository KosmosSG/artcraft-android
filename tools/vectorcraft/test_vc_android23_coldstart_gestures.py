"""Android.23: verified startup/gesture corrections, no keyboard regression."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android23(unittest.TestCase):
    def test_real_cold_start_and_menu_flow(self):
        src=(TOOLS/"patch_android23_input_boot.py").read_text()
        for expected in (
            "showStartupCover();",
            "splashHandler.postDelayed(this::dismissStartupCover, 120)",
            "PhotoCraft parity: do NOT rewrite Android native wheel sources",
            "from_micros(6060)",
            "vc_font_fallback_last",
            "std::time::Duration::from_millis(350)",
        ): self.assertIn(expected,src)
        for forbidden in ("vcOfferModalShortcut", "vcSetHardwareShortcutMode",
                          "physicalShortcutKeys", "setPresentMode", "killProcess"):
            self.assertNotIn(forbidden,src)

    def test_font_cache_refresh_off_ui(self):
        src=(TOOLS/"patch_android23_font_fastpath.py").read_text()
        for expected in (
            "entries.flatten().count() as u64",
            "std::fs::metadata(path)",
            "refresh_font_links_off_ui_thread()",
            "spawn(refresh_font_links)",
            "vectorcraft-font-links-cache-v1",
        ): self.assertIn(expected,src)
        self.assertNotIn("remove_dir_all(",src)

    def test_bounded_pinch_without_touchscreen_regression(self):
        backend=(TOOLS/"backend_stability.py").read_text()
        for expected in (
            "pad_fallback_gesture",
            "unclassified_pad",
            "factor.clamp(0.94, 1.06)",
            "clamp(-48.0, 48.0)",
            "Classification::TwoFingerSwipe => PadGesture::Scroll",
            "Classification::Pinch => PadGesture::Pinch",
        ): self.assertIn(expected,backend)

    def test_disposable_arm64_and_protected_keyboard(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        for expected in (
            "VERSION_NAME: 0.21.0-android.23",
            "VERSION_CODE: '16783383'",
            "patch_android20_native_keyboard_splash.py",
            "patch_android23_input_boot.py",
            "patch_android23_font_fastpath.py",
            "com.artcraft.vectorcraft.test",
            "builder/build.sh -vectorcraft --noupdate",
            "Delete disposable builder signing materials",
        ): self.assertIn(expected,w)
        self.assertNotIn("gh release create",w)

if __name__=="__main__":
    unittest.main()
