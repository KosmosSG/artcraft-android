"""Static source-only guard for VectorCraft Android.9 wheel controls.

Verify persistence remains backwards-compatible with Android.8 eight-index
layout strings, and hit testing/clamping scale with the rendered wheel.
No CI toolchain or Rust compile needed.
"""
from pathlib import Path
import unittest

WHEEL = Path(__file__).resolve().parent / "stylus_wheel.rs"


class Android9WheelPreferences(unittest.TestCase):
    def test_controls_and_defaults(self):
        s = WHEEL.read_text()
        for expected in (
            "size_percent: 100, opacity_percent: 100",
            'egui::Label::new("Wheel Size")',
            'egui::Label::new("Opacity")',
            "75..=140", "30..=100",
            "self.size_percent = 100;",
            "self.opacity_percent = 100;",
        ):
            self.assertIn(expected, s)

    def test_loads_legacy_and_new_persisted_values(self):
        s = WHEEL.read_text()
        for expected in (
            "values.len() == 8 || values.len() == 10",
            "values[..8].iter().all",
            "self.layout.copy_from_slice(&values[..8])",
            "self.size_percent = values[8] as u32;",
            "self.opacity_percent = values[9] as u32;",
            'saved.push_str(&format!(",{},{}", self.size_percent, self.opacity_percent))',
            "self.layout_dirty = true;",
        ):
            self.assertIn(expected, s)

    def test_hit_target_and_visuals_both_scale(self):
        s = WHEEL.read_text()
        for expected in (
            "let inset = SIZE * self.size_percent as f32 / 200.0 + 10.0;",
            "let vector = (pos - center) * (100.0 / self.size_percent as f32);",
            "let scale = (0.86 + 0.14 * t) * self.size_percent as f32 / 100.0;",
            "let opacity = self.opacity_percent as f32 / 100.0;",
            "Color32::BLACK.gamma_multiply(softness * opacity)",
            "hub_burgundy.gamma_multiply(opacity)",
            "Color32::WHITE.gamma_multiply(opacity)",
        ):
            self.assertIn(expected, s)


if __name__ == "__main__":
    unittest.main()
