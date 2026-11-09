"""VectorCraft Android.22: protected high-refresh, ANR instrumentation and pad gestures."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/"tools/vectorcraft"

class Android22(unittest.TestCase):
    def test_165hz_is_preference_not_forced(self):
        src=(TOOLS/"patch_android22_high_refresh.py").read_text()
        for marker in ("vcRefreshRateHint", "getSupportedModes()", "getCurrentThermalStatus",
                       "isPowerSaveMode()", "preferredRefreshRate=chosen",
                       "Math.min(limit, 90f)", "Math.min(limit, 120f)",
                       "mode.getRefreshRate() <= 165.5f", "VC_PERF_UI_PROXY",
                       "VC_UI_STALL", "vc_prune_last", "from_micros(6060)"):
            self.assertIn(marker,src)
        for unsafe in ("setFrameRate(165", "setPresentMode(IMMEDIATE", "vsync: false",
                       "System.exit(", "killProcess(", "android_owner_unsaved_key"):
            self.assertNotIn(unsafe,src)

    def test_unclassified_trackpad_fallback_scoped(self):
        src=(TOOLS/"backend_stability.py").read_text()
        for marker in ("reported_pad_gesture", "unclassified_pad",
                       "pad_fallback_gesture", "motion_event.pointer_count() >= 2",
                       "self.pad_fallback_gesture=PadGesture::Pinch",
                       "self.pad_fallback_gesture=PadGesture::Scroll",
                       "if unclassified_pad && pad_gesture==PadGesture::None",
                       "return input_status;"):
            self.assertIn(marker,src)
        self.assertIn("Classification::TwoFingerSwipe => PadGesture::Scroll",src)
        self.assertIn("Classification::Pinch => PadGesture::Pinch",src)

    def test_approved_shortcuts_and_release_gates(self):
        w=(ROOT/".github/workflows/vectorcraft-stability-test-apk.yml").read_text()
        self.assertIn("VERSION_NAME: 0.21.0-android.23",w)
        self.assertIn("VERSION_CODE: '16783383'",w)
        self.assertIn("patch_android20_native_keyboard_splash.py",w)
        self.assertIn("patch_android21_photocraft_parity.py",w)
        self.assertIn("patch_android22_high_refresh.py",w)
        self.assertIn("com.artcraft.vectorcraft.test",w)
        self.assertIn("builder/build.sh -vectorcraft --noupdate",w)
        self.assertIn("Delete disposable builder signing materials",w)
        self.assertNotIn("gh release create",w)
        owner=(TOOLS/"patch_android22_high_refresh.py").read_text()
        self.assertNotIn("vcSetHardwareShortcutMode",owner)
        self.assertNotIn("vcOfferModalShortcut",owner)
        self.assertNotIn("clearFocus()",owner)

if __name__=="__main__":
    unittest.main()
