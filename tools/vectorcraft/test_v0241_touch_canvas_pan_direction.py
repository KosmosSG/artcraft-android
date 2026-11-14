"""Regression guard for the next HONOR MagicPad two-finger canvas pan test.

This is a source-level check only. It does NOT establish actual on-device
finger direction, pinch behavior or app correctness. Keep the ongoing Android.10
IME build separate from this next-test candidate.
"""
from pathlib import Path
import unittest


class TouchscreenCanvasPanDirectionTests(unittest.TestCase):
    def test_reversal_is_guarded_and_applies_to_both_touch_sources(self):
        source = (Path(__file__).parent / "patch_android8_wheel_touch.py").read_text()
        # The Android-only canvas branch must select one touch source before
        # reversing; no global MouseWheel or trackpad sign change is allowed.
        marker = "if early_two_touch_on_canvas || native_canvas_touch.is_some() {"
        self.assertEqual(source.count(marker), 1)
        guarded = source.split(marker, 1)[1].split("};", 1)[0]
        self.assertIn("-early_pan", guarded)
        self.assertIn("-native_canvas_touch.map_or(egui::Vec2::ZERO, |t| t.translation_delta)", guarded)
        self.assertIn("rect.contains(t.center_pos)", source)
        self.assertEqual(source.count("if early_pan != egui::Vec2::ZERO"), 1)

    def test_pinch_and_trackpad_are_not_reversed_by_patch(self):
        source = (Path(__file__).parent / "patch_android8_wheel_touch.py").read_text()
        # This single-point replacement must not touch wheel zoom factor or
        # native trackpad routing. Those stay independently device-tested.
        before = source.split("let native_canvas_touch = ui.input(|i| i.multi_touch())", 1)[0]
        self.assertIn("Keep the upstream wheel's pinch zoom unchanged.", before)
        # No global inversion of the entire wheel/trackpad scroll stream.
        self.assertNotIn("scroll = -scroll", source)
        self.assertNotIn("delta.x *= 1.15", source)
        self.assertNotIn("delta.y *= 1.15", source)
        # Both negations are in the touchscreen-only branch, not applied to
        # wheel or trackpad data outside that branch.
        self.assertEqual(source.count("-early_pan"), 1)
        self.assertEqual(source.count("-native_canvas_touch.map_or"), 1)


if __name__ == "__main__":
    unittest.main()
