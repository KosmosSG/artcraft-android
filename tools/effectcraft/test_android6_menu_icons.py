"""Static guards for EffectCraft Android.6 menu and wheel icon polish.

The checks do not pretend to verify physical pen input; that remains a device test.
"""
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent

class WheelMenuPolishTests(unittest.TestCase):
    def test_existing_menu_divider_used_once(self):
        src = (HERE / "patch_stylus_wheel.py").read_text()
        start = src.index("    # Integrate with existing compact Ec menu")
        end = src.index("    (source / \"stylus_wheel.rs\")", start)
        injected = src[start:end]
        self.assertIn("Do not insert a second divider before Stylus Wheel.", injected)
        self.assertNotIn("ui.separator();\n                        let wheel_on", injected)

    def test_new_vector_icons_replace_wand_and_tiny_hand(self):
        wheel = (HERE / "stylus_wheel.rs").read_text()
        self.assertIn("0 => { // Effect: the editor's own precise", wheel)
        self.assertIn("Icon::Fx, color", wheel)
        self.assertIn("4 => { // Hand: clean outlined open palm", wheel)
        self.assertIn("Four distinct fingertip arcs", wheel)
        self.assertIn("finger(8.2, 10.6", wheel)
        self.assertIn("finger(16.2, 18.6", wheel)
        self.assertNotIn("uniform magic wand with three clean sparkle crosses", wheel)

    def test_protected_android5_features_remain(self):
        wheel = (HERE / "stylus_wheel.rs").read_text()
        for snippet in (
            'include_bytes!("stylus_wheel_ec.rgba")',
            "vec2(42.5, 28.05) * scale",
            "size_percent: 75.0, opacity_percent: 85.0",
            "self.size_percent = 75.0;",
            "ec-stylus-hover-dot",
        ):
            self.assertIn(snippet, wheel)
        menu = (HERE / "patch_wheel_photocraft_parity.py").read_text()
        self.assertIn('ui.menu_button("App Updates"', menu)
        self.assertIn('ui.menu_button("Stylus Wheel"', menu)

if __name__ == "__main__":
    unittest.main()
