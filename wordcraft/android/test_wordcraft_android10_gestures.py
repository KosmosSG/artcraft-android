"""Static Android.10 gesture/menu gates, run before SDK installation.

These assertions check source integration only. They do not establish
HONOR MagicPad trackpad functionality or guarantee screen smoothness.
"""
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class WordCraftAndroid10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = (HERE / "WordCraftExtension.java.inc").read_text()
        cls.rust = (HERE / "wordcraft_android.rs").read_text()
        cls.menu = (HERE / "ribbon_android.rs.inc").read_text()
        cls.builder = (HERE / "patch_builder.py").read_text()

    def test_android14_classified_touchpad_single_pointer_gestures(self):
        j = self.java
        for marker in (
            "WC_ANDROID10_CLASSIFIED_TRACKPAD_V1",
            "wcDispatchClassifiedTrackpad(android.view.MotionEvent event)",
            "CLASSIFICATION_TWO_FINGER_SWIPE",
            "CLASSIFICATION_PINCH",
            "AXIS_GESTURE_SCROLL_X_DISTANCE",
            "AXIS_GESTURE_SCROLL_Y_DISTANCE",
            "AXIS_GESTURE_PINCH_SCALE_FACTOR",
            "getHistoricalAxisValue(",
            "event.getHistorySize()",
            "wcClassifiedTrackpadActive",
            "wcMarkTrackpadNavigation()",
            "wcScrollZoom",
            "wcTouchNavSuppressInk || wcTrackpadNavigationActive()",
        ):
            self.assertIn(marker, j, marker)
        self.assertLess(j.index("if (wcDispatchClassifiedTrackpad(event)) return true;"),
                        j.index("if (wcDispatchTrackpadFingers(event)) return true;"))
        self.assertIn("if (wcDispatchClassifiedTrackpad(event)) return true;", j.split(
            "@Override public boolean dispatchGenericMotionEvent", 1)[1])
        self.assertIn("super.dispatchTouchEvent(cancel)", j)
        self.assertIn("return true;", j.split("// Gesture is consumed here", 1)[1])
        self.assertIn("wcScrollZoom = 1f;", j)

    def test_native_zoom_is_distinct_from_trackpad_scroll(self):
        n = self.rust
        part = n.split("pub fn inject_trackpad_scroll(", 1)[1].split(
            "pub fn inject_stylus_motion(", 1)[0]
        self.assertIn("WC_ANDROID10_TRACKPAD_PINCH_RUST_V1", part)
        self.assertIn("Some(zoom)", part)
        self.assertIn("egui::Event::Zoom(zoom.clamp(0.5, 2.0))", part)
        self.assertIn("if dx != 0.0 || dy != 0.0", part)
        self.assertIn("egui::MouseWheelSource::Trackpad", part)
        self.assertNotIn("egui::Event::Touch {", part)
        self.assertIn("raw.events.retain", part)

    def test_touchscreen_horizontal_pan_stability_and_early_pinch(self):
        j = self.java
        self.assertIn("wcTouchNavConsuming = true", j)
        self.assertIn("wcTouchNavSuppressInk = true", j)
        self.assertIn("float spanStep = Math.abs(span - wcTouchLastSpan)", j)
        self.assertIn("float centerStep = (float) Math.hypot(dx, dy)", j)
        self.assertIn("wcTouchStartSpan * .03f", j)
        self.assertIn("wcTouchPinchEvidence >= 2", j)
        self.assertIn("spanStep > Math.max(2.0f, centerStep * 1.2f)", j)
        self.assertIn("wcTouchPanX += dx * .80f + wcTouchPreviousPanX * .20f;", j)
        self.assertIn("wcTouchZoom * Math.max(.75f, Math.min(1.33f, ratio))", j)
        self.assertIn("event.getHistoricalX(0, historyIndex)", j)

    def test_pressure_is_on_by_default_without_menu_clutter(self):
        j = self.java
        menu = self.menu
        self.assertIn("WC_ANDROID10_PRESSURE_DEFAULT_ON_V1", j)
        self.assertIn('getBoolean("pressure_ink", true)', j)
        self.assertIn("wcSetPressureInkEnabled(boolean on)", j)
        self.assertNotIn('ui.menu_button("Stylus & Handwriting"', menu)
        self.assertIn("WC_ANDROID10_COMPACT_MENU_V1", menu)
        for row in ('ui.menu_button("App Updates"', 'ui.menu_button("Appearance"',
                    'ui.menu_button("Keyboard & Shortcuts"',
                    'ui.menu_button("About WordCraft"'):
            self.assertEqual(menu.count(row), 1, row)
        for marker in ("wcStylusStatus", "wcTakeStylusTrail", "wcStylusHoverPosition"):
            self.assertIn(marker, j)
        self.assertIn("apply_pressure_ink", self.builder)
        self.assertIn("apply_touch_guard", self.builder)


if __name__ == "__main__":
    unittest.main()
