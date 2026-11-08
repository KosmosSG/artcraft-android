"""EffectCraft Android.13 HONOR Smart Touch input routing regression guards.

User evidence: Android.12 473-event native log, Mouse/Finger Down->Cancel
bursts, nonzero scroll51 in Move and 82 dual-touchscreen Move samples.
These checks are source contracts; real ARM64 compilation + tablet test follow.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from patch_android13_input import apply, ANCHOR, INSERT

class MagicOSTrackpadTest(unittest.TestCase):
    def fixture(self, folder):
        path = Path(folder) / "src/platform_impl/android/mod.rs"
        path.parent.mkdir(parents=True)
        path.write_text(
            "fn input() {\n"
            "MotionAction::Move if pointer_class\n"
            "Axis::__Unknown(51)\n"
            "MouseInput\n"
            "MotionAction::Cancel\n"
            + ANCHOR + "\n}"
        )
        return path

    def test_native_patch_preserves_click_and_pinch(self):
        with TemporaryDirectory() as d:
            path=self.fixture(d)
            apply(Path(d))
            src=path.read_text()
            self.assertIn('motion_event.button_state().0 & 1', src)
            self.assertIn('tool_type == ToolType::Finger', src)
            self.assertIn('motion_event.source(), Source::Mouse', src)
            self.assertIn('EC13_PAD_CONTACT', src)
            self.assertIn('MotionAction::Down if motion_event.pointer_count() == 1', src)
            self.assertIn('MotionAction::PointerDown if motion_event.pointer_count() >= 2', src)
            self.assertIn('MotionAction::Cancel', src)
            self.assertIn('MotionAction::Up', src)
            self.assertIn('MotionAction::Move if motion_event.pointer_count() == 1', src)
            self.assertIn('Axis::__Unknown(50)', src)
            self.assertIn('Axis::__Unknown(51)', src)
            self.assertIn('Axis::__Unknown(52)', src)
            self.assertIn('event::MouseScrollDelta::PixelDelta', src)
            self.assertIn('event::ElementState::Pressed', src)
            self.assertIn('event::ElementState::Released', src)
            self.assertIn('return InputStatus::Handled;', src)
            self.assertIn('if direct {', src)
            # No changes to touchscreen/stylus or normal Mouse tool input.
            self.assertIn('tool_type == ToolType::Finger', src)
            self.assertNotIn('Source::Touchscreen &&', INSERT)
            self.assertNotIn('ToolType::Stylus', INSERT)
            self.assertIn('MotionAction::Move if pointer_class', src)
            with self.assertRaisesRegex(RuntimeError, "already staged"):
                apply(Path(d))

    def test_drift_fails_closed(self):
        with TemporaryDirectory() as d:
            path=self.fixture(d)
            path.write_text("upstream changed")
            with self.assertRaisesRegex(RuntimeError, "drift"):
                apply(Path(d))
            self.assertEqual(path.read_text(),"upstream changed")

if __name__=="__main__":
    unittest.main()
