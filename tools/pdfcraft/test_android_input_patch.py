"""The PDFCraft two-finger and hardware modifier source patch is exact and idempotent."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"/"pdfcraft"))
from android_input_patch import patch
from winit_v015_compat import with_ime_api

class AndroidInputCompatibility(unittest.TestCase):
    def test_pinned_vendor_input_overlay(self):
        source=(ROOT/"vendor"/"winit"/"src"/"platform_impl"/"android"/"mod.rs").read_text()
        patched=patch(with_ime_api(source))
        self.assertEqual(patch(patched),patched)
        for needle in [
            "fn pdfcraft_android_gesture",
            "MotionAction::PointerDown if count >= 2",
            "MouseScrollDelta::PixelDelta",
            "PdfTouchMode::Scroll",
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

if __name__=="__main__":
    unittest.main()
