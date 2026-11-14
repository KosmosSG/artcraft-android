"""Fail-closed static guards for EffectCraft Android.5 visual/hover refinements.
Actual stylus proximity and screen mapping still require MagicPad 4 device tests.
"""
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

class Android5HoverWheelGuards(unittest.TestCase):
    def test_pen_hover_does_not_require_stylus_button_device_id(self):
        s = (HERE / "patch_stylus_native.py").read_text()
        hover = s.split("pub fn ec_stylus_native_hover(", 1)[1].split(
            "pub fn ec_stylus_native_hover_point(", 1)[0]
        self.assertNotIn("state.allowed.contains(&device)", hover)
        self.assertIn("source & 0x00004002", hover)
        self.assertIn("tool != 2 && tool != 4", hover)
        self.assertIn("7 | 9", hover)
        self.assertIn("10 | 0 | 1 | 3", hover)
        capture = s.split("pub fn ec_stylus_native_capture(", 1)[1].split(
            "pub fn ec_stylus_native_hover(", 1)[0]
        self.assertIn("!state.allowed.contains(&device)", capture)

    def test_java_fallback_is_precontact_and_non_consuming(self):
        s = (HERE / "patch_stylus_wheel.py").read_text()
        self.assertIn("dispatchGenericMotionEvent(", s)
        self.assertIn("event.isFromSource(android.view.InputDevice.SOURCE_STYLUS)", s)
        self.assertIn("return super.dispatchGenericMotionEvent(event)", s)
        self.assertIn("return super.onGenericMotionEvent(event)", s)
        self.assertIn("ec_stylus_native_hover_point()", s)

    def test_logo_and_icons_preserve_fidelity(self):
        s = (HERE / "stylus_wheel.rs").read_text()
        self.assertIn("vec2(42.5, 28.05) * scale", s)
        self.assertIn('include_bytes!("stylus_wheel_ec.rgba")', s)
        self.assertIn("Uniform, 24-point, crisp white vector symbols", s)
        self.assertIn("Lucide-style Undo2 / Redo2", s)
        self.assertIn("PhotoCraft", s)
        self.assertIn("if let Some(pos) = self.pen_hover", s)
        self.assertIn("size_percent: 75.0, opacity_percent: 85.0", s)
        self.assertIn("self.size_percent = 75.0;", s)

if __name__ == "__main__":
    unittest.main()
