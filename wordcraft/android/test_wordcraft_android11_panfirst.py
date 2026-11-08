"""WordCraft Android.11 source gates + deterministic gesture acceptance cases.

The tiny Python model checks desired gesture decisions, while source assertions
ensure the actual Java bridge retains the same safeguards. Hardware smoothness
and MagicOS delivery still require physical tablet tests.
"""
import math
import unittest
from pathlib import Path

HERE = Path(__file__).parent


def classify_samples(points):
    """Model Android.11 pan-first thresholds for motion design regression."""
    mode, evidence = 1, 0
    span0 = math.dist(points[0][0], points[0][1])
    prior = points[0]
    prior_span = span0
    for f0, f1 in points[1:]:
        span = math.dist(f0, f1)
        cx = (f0[0] + f1[0]) * .5
        cy = (f0[1] + f1[1]) * .5
        px = (prior[0][0] + prior[1][0]) * .5
        py = (prior[0][1] + prior[1][1]) * .5
        center_step = math.hypot(cx - px, cy - py)
        span_step = abs(span - prior_span)
        d0 = (f0[0] - prior[0][0], f0[1] - prior[0][1])
        d1 = (f1[0] - prior[1][0], f1[1] - prior[1][1])
        opposed = d0[0] * d1[0] + d0[1] * d1[1] < 0
        dominant = span_step > max(2, center_step * 1.2) and (
            opposed or center_step < span_step * .7
        )
        intentional = dominant and abs(span - span0) > max(11, span0 * .03)
        if mode == 1:
            evidence = min(3, evidence + 1) if intentional else 0
            if evidence >= 2:
                mode = 2
        prior, prior_span = (f0, f1), span
    return mode


class Android11PanFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = (HERE / "WordCraftExtension.java.inc").read_text()
        cls.menu = (HERE / "ribbon_android.rs.inc").read_text()
        cls.native = (HERE / "wordcraft_android.rs").read_text()

    def test_parallel_horizontal_and_vertical_pan_never_zoom(self):
        x = [((50 + d, 80), (200 + d, 80)) for d in (0, 4, 10, 18, 25, 34)]
        y = [((50, 80 + d), (200, 80 + d)) for d in (0, 4, 10, 18, 25, 34)]
        self.assertEqual(classify_samples(x), 1)
        self.assertEqual(classify_samples(y), 1)

    def test_opposing_finger_pinch_switches_after_two_samples(self):
        seq = [((50 - d, 80), (200 + d, 80)) for d in (0, 2, 5, 9, 15)]
        self.assertEqual(classify_samples(seq[:3]), 1)
        self.assertEqual(classify_samples(seq), 2)

    def test_moderate_span_jitter_does_not_switch_to_pinch(self):
        seq = [((50 + d, 80), (200 + d + eps, 80))
               for d, eps in zip((0, 6, 13, 20, 26), (0, 1, -1, 2, 0))]
        self.assertEqual(classify_samples(seq), 1)

    def test_java_integrates_pan_first_hysteresis_and_horizontal_filter(self):
        j = self.java
        for marker in (
            "WC_ANDROID11_PAN_FIRST_PINCH_HYSTERESIS_V1",
            "wcTouchMode = 1; // Two-finger pan immediately",
            "wcTouchPinchEvidence = 0;",
            "wcTouchPinchEvidence >= 2",
            "spanStep > Math.max(2.0f, centerStep * 1.2f)",
            "opposed || centerStep < spanStep * .7f",
            "wcTouchStartSpan * .03f",
            "wcTouchPanX += dx * .80f + wcTouchPreviousPanX * .20f;",
            "wcTouchPanY += dy;",
            "event.getHistoricalX(0, historyIndex)",
            "wcTouchNavSuppressInk = true",
            "wcTouchNavigationCancellingInk()",
            "wcDispatchClassifiedTrackpad(event)",
        ):
            self.assertIn(marker, j, marker)
        self.assertIn('getBoolean("pressure_ink", true)', j)
        self.assertIn("egui::Event::Zoom(", self.native)

    def test_appearance_has_one_theme_selector_and_separate_dark_pages(self):
        menu = self.menu
        self.assertIn("WC_ANDROID11_APPEARANCE_SINGLE_THEME_V1", menu)
        self.assertNotIn('ui.checkbox(&mut dark, "Dark mode")', menu)
        self.assertEqual(menu.count('ui.menu_button("Theme preferences (System / Light / Dark)"'), 1)
        self.assertIn('ui.checkbox(&mut dark_page, "Dark document pages")', menu)
        self.assertNotIn('ui.menu_button("Stylus & Handwriting"', menu)
        self.assertIn('ui.menu_button("App Updates"', menu)
        self.assertIn('ui.menu_button("Keyboard & Shortcuts"', menu)


if __name__ == "__main__":
    unittest.main()
