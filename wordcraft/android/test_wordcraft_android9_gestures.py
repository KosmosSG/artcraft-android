"""Android.9 source regression gates; executed before expensive Android setup.

These checks document what the candidate must preserve. Passing them does
not substitute for device testing with the HONOR MagicPad trackpad.
"""
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Android9GestureGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = (HERE / "WordCraftExtension.java.inc").read_text()
        cls.native = (HERE / "wordcraft_android.rs").read_text()
        cls.builder = (HERE / "patch_builder.py").read_text()
        cls.guard = (HERE / "patch_touch_guard.py").read_text()

    def test_pinch_is_detected_early_even_after_pan(self):
        j = self.java
        self.assertIn("WC_ANDROID9_PINCH_TRACKPAD_GUARD_V1", j)
        self.assertIn("wcTouchMode != 2 && distanceChange > threshold", j)
        self.assertIn("wcTouchStartSpan * .012f", j)
        self.assertIn("distanceChange > centerTravel * .55f", j)
        self.assertIn("wcTouchPanX = wcTouchPanY = 0f", j)
        self.assertIn("wcTouchZoom * Math.max(.75f, Math.min(1.33f, ratio))", j)
        self.assertIn("wcTouchMode = 1", j)
        self.assertIn("wcTouchMode = 2", j)

    def test_touchpad_multi_contacts_cannot_select_text_or_draw_ink(self):
        j = self.java
        self.assertIn("wcDispatchTrackpadFingers(event)", j)
        self.assertLess(
            j.index("if (wcDispatchTrackpadFingers(event)) return true;"),
            j.index("if (wcRejectPalm(event)) return true;")
        )
        self.assertIn("SOURCE_TOUCHPAD", j)
        self.assertIn("SOURCE_MOUSE", j)
        self.assertIn("wcTrackpadPairConsuming", j)
        self.assertIn("wcTrackpadPairActive", j)
        self.assertIn("super.dispatchTouchEvent(cancel)", j)
        self.assertIn("wcMarkTrackpadNavigation()", j)
        self.assertIn("wcTrackpadNavigationActive()", j)
        self.assertIn("wcTouchNavSuppressInk || wcTrackpadNavigationActive()", j)
        self.assertIn("wcTrackpadNavUntilMs = 0L", j)
        self.assertIn("wcScrollX += dx", j)
        self.assertIn("wcScrollY += dy", j)
        self.assertIn("ACTION_UP", j)
        self.assertIn("ACTION_CANCEL", j)

    def test_native_trackpad_scroll_releases_editor_pointer_not_draws(self):
        n = self.native
        self.assertIn("WC_ANDROID9_TRACKPAD_NO_DRAG_RUST_V1", n)
        method = n.split("pub fn inject_trackpad_scroll(", 1)[1].split(
            "pub fn inject_stylus_motion(", 1
        )[0]
        self.assertIn("raw.events.retain(|event| !matches!(event,", method)
        self.assertIn("egui::PointerButton::Primary, pressed: true", method)
        self.assertIn("pressed: false", method)
        self.assertLess(method.index("pressed: false"), method.index("egui::Event::MouseWheel {"))
        self.assertIn("egui::MouseWheelSource::Trackpad", method)
        self.assertNotIn("egui::Event::Touch {", method)

    def test_stylus_and_android8_touchscreen_cancel_not_removed(self):
        j, n = self.java, self.native
        for token in ("wcOnlyFingers(event)", "wcCaptureStylusHistory(event)",
                      "wcRecordStylus(event)", "wcRejectPalm(event)",
                      "wcTouchNavConsuming = true", "wcTouchNavSuppressInk = true",
                      "wcTouchNavigationCancellingInk()",
                      "event.getHistoricalX(0, historyIndex)"):
            self.assertIn(token, j, token)
        for token in ("inject_stylus_motion", "wc_stylus.path_samples",
                      "wc_stylus.hover_pos", "egui::Event::Zoom(",
                      "wc_touchnav.suppress_ink"):
            self.assertIn(token, n, token)
        self.assertIn("apply_touch_guard", self.builder)
        self.assertIn("app.canvas.cancel_text_drag()", self.guard)
        self.assertIn("app.canvas.ink = None", self.guard)


if __name__ == "__main__":
    unittest.main()
