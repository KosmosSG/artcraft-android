"""Regression: Android.14 glass two-finger pan/zoom + canvas selection guard."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from patch_android14_glass import apply, ANCHOR

class GlassNavigationTests(unittest.TestCase):
    def test_native_touchscreen_only_and_real_selection_protection(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            path=root/"src/platform_impl/android/mod.rs"
            path.parent.mkdir(parents=True)
            path.write_text("\n".join([
                "EC13_PAD_CONTACT", "MotionAction::Move if pointer_class",
                "MotionAction::Scroll => {", "Axis::__Unknown(51)",
                "MouseInput", "MotionAction::Cancel",
                ANCHOR, "}"]))
            apply(root)
            data=path.read_text()
            self.assertIn("Source::Touchscreen",data)
            self.assertIn("tool_type == ToolType::Finger",data)
            self.assertIn("!pointer_class",data)
            self.assertIn("EC14_GLASS",data)
            self.assertIn("motion_event.pointer_count() >= 2",data)
            self.assertIn("MotionAction::PointerDown",data)
            self.assertIn("event::TouchPhase::Cancelled",data)
            self.assertIn("return InputStatus::Handled;",data)
            self.assertIn("MouseScrollDelta::PixelDelta",data)
            self.assertIn("PinchGesture",data)
            self.assertIn("delta: scale.ln()",data)
            self.assertIn("move_from_origin > 12.0",data)
            self.assertIn("spread_change > 36.0",data)
            self.assertIn("spread_change > 1.5 * move_from_origin",data)
            self.assertIn("MotionAction::Move if pointer_class",data)
            with self.assertRaisesRegex(RuntimeError,"already applied"):
                apply(root)

    def test_fail_closed_on_base_drift(self):
        with TemporaryDirectory() as td:
            root=Path(td);path=root/"src/platform_impl/android/mod.rs"
            path.parent.mkdir(parents=True)
            path.write_text(ANCHOR)
            with self.assertRaisesRegex(RuntimeError,"working gesture bridge"):
                apply(root)
            self.assertEqual(path.read_text(),ANCHOR)

    def test_egui_canvas_guards_scroll_while_wheel_active(self):
        root=Path(__file__).parent
        source=(root/"patch_android_menu_scroll.py").read_text()
        self.assertIn("effectcraft.android14.canvas.scroll_until",source)
        self.assertIn("ec14_now + 0.18_f64",source)
        self.assertIn("scroll_until >= ctx.input(|i| i.time)",source)
        self.assertIn("egui::MouseWheelUnit::Point",source)
        self.assertIn("if !ec_navigating {",source)
        self.assertIn('d.remove::<Gesture>(egui::Id::unique("viewer-gesture"))',source)
        self.assertIn("android_record_menu_scroll(ui, &out",source)
        # The old Android.13 pointer source and click fallbacks remain intact.
        self.assertIn("EC13_PAD_CONTACT",(root/"patch_android13_input.py").read_text())

if __name__=="__main__":
    unittest.main()
