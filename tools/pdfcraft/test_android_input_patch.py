"""The PDFCraft two-finger and hardware modifier source patch is exact and idempotent."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"/"pdfcraft"))
from android_input_patch import patch
from android_onefinger_patch import patch as patch_onefinger
from android_trackpad_patch import patch as patch_trackpad
from winit_v015_compat import with_ime_api

class AndroidInputCompatibility(unittest.TestCase):
    def test_pinned_vendor_input_overlay(self):
        source=(ROOT/"vendor"/"winit"/"src"/"platform_impl"/"android"/"mod.rs").read_text()
        patched=patch_trackpad(patch_onefinger(patch(with_ime_api(source))))
        self.assertEqual(patch_trackpad(patch_onefinger(patch(patched))),patched)
        for needle in [
            "fn pdfcraft_android_gesture",
            "MotionAction::PointerDown if count >= 2",
            "MouseScrollDelta::PixelDelta",
            "event::WindowEvent::CursorMoved { device_id, position: mid }",
            "motion_event.source() == Source::Touchscreen",
            "PDFCRAFT_ANDROID_ONE_FINGER_NAVIGATION",
            "PdfTouchMode::SinglePan",
            "PdfTouchMode::SingleSelect",
            "std::time::Duration::from_millis(300)",
            "PDFCRAFT_ANDROID_TRACKPAD_SCROLL",
            "PDFCRAFT_ANDROID_PRECISE_TRACKPAD_SCROLL",
            "PDFCRAFT_ANDROID_GESTURE_AXES_34",
            "PDFCRAFT_ANDROID_TRACKPAD_SCROLL_LOCK",
            "PDFCRAFT_ANDROID_TRACKPAD_PHASED_SCROLL",
            "pdfcraft_trackpad_pan_active",
            "phase: event::TouchPhase::Started",
            "phase: event::TouchPhase::Ended",
            "expanded > (initial_spread*0.12).max(30.0)",
            "expanded > 2.5 * translated",
            "android_app.enable_motion_axis(Axis::from(50u32))",
            "android_app.enable_motion_axis(Axis::from(51u32))",
            "pointer.axis_value(Axis::from(50u32))",
            "pointer.axis_value(Axis::from(51u32))",
            "has_gesture_scroll",
            "x: (-gesture_axes.0).clamp(",
            "y: (-gesture_axes.1).clamp(",
            "fractional_scroll",
            "point_count >= 2",
            "precision_trackpad = touchpad_source",
            "(has_scroll_axes || has_gesture_scroll) && axis_action",
            "Source::Touchpad | Source::TouchNavigation",
            "PdfTouchMode::Scroll",
            "event::WindowEvent::PanGesture",
            "travelled > 6.0",
            ".clamp(-0.06, 0.06)",
            "Source::TouchNavigation",
            "Source::MouseRelative",
            "TouchPhase::Cancelled",
            "PinchGesture",
            "key.meta_state()",
            "meta.ctrl_on()",
            "ModifiersChanged(mods.into())",
            "self.pdfcraft_android_key_modifiers(key, callback);",
        ]:
            self.assertIn(needle,patched)
        self.assertIn("tool_type == ToolType::Finger",patched)
        self.assertIn("self.pdfcraft_touch_held = false",patched)
        self.assertIn("return input_status;",patched)
        self.assertIn("MotionAction::Move",patched)
        self.assertIn("MouseScrollDelta::LineDelta(horizontal, vertical)",patched)
        self.assertNotIn("points: Vec<_> = motion_event.pointers()",patched)
        # A scroll gesture cannot switch to pinch once latched.
        self.assertIn("&& !self.pdfcraft_trackpad_pan_active",patched)
        # Old, hypersensitive trackpad pinch threshold must not reappear.
        self.assertNotIn("expanded > (initial_spread*0.04).max(12.0)",patched)

if __name__=="__main__":
    unittest.main()
