"""EffectCraft-only pinned-winit native MotionEvent diagnostic anchors."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from patch_android_motion_diag import apply, ANCHOR, FFI_ANCHOR

class GestureEventCaptureTests(unittest.TestCase):
    def test_motion_hook_preserves_existing_routes(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            target = root / "src/platform_impl/android/mod.rs"
            target.parent.mkdir(parents=True)
            target.write_text("fn f() { MotionAction::Scroll => { } MotionAction::Move if pointer_class { } Axis::__Unknown(50); Axis::__Unknown(52);\n"
                              + FFI_ANCHOR + "\n" + ANCHOR + "\n}")
            apply(root)
            data = target.read_text()
            self.assertIn("EC10 event action=", data)
            self.assertIn("motion_event.pointer_count()", data)
            self.assertIn('unsafe extern "C"', data)
            self.assertIn('__android_log_write(', data)
            self.assertIn('EffectCraftMotion', data)
            self.assertIn('EC10_MOVE_COUNT', data)
            self.assertIn('MotionAction::Scroll => true', data)
            self.assertNotIn('&& (pointer_class ||', data)
            self.assertIn("Axis::__Unknown(48)", data)
            self.assertIn("Axis::__Unknown(49)", data)
            self.assertIn("Axis::__Unknown(50)", data)
            self.assertIn("Axis::__Unknown(51)", data)
            self.assertIn("Axis::__Unknown(52)", data)
            self.assertIn("MotionAction::Move if pointer_class", data)
            self.assertNotIn("pointer.x()", data)
            self.assertNotIn("pointer.y()", data)
            with self.assertRaisesRegex(RuntimeError, "already applied"):
                apply(root)

    def test_drift_refuses_without_partial_mutation(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            target = root / "src/platform_impl/android/mod.rs"
            target.parent.mkdir(parents=True)
            target.write_text("source changed")
            with self.assertRaisesRegex(RuntimeError, "drift"):
                apply(root)
            self.assertEqual(target.read_text(), "source changed")
