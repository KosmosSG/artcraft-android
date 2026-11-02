"""Guarded PDFCraft native Select/toolbar keyboard source patches."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"tools"/"pdfcraft"/"android_canvas_input_patch.py"
class NativeTouchAndTools(unittest.TestCase):
    def test_source_contains_strict_guards(self):
        s=SRC.read_text()
        for check in ("PDFCRAFT_ANDROID_SELECT_TOUCH_NOT_SCROLL", "DragScroll::Never",
            "DragScroll::OnTouch", "PDFCRAFT_ANDROID_BARE_TOOL_KEYS", "self.android_bare_tool_keys(ctx);",
            "ctx.text_edit_focused()", "Key::H", "Key::V",
            "QuickTool::Hand", "QuickTool::Select", "ctx.input_mut"):
            self.assertIn(check,s)
if __name__=="__main__": unittest.main()

class SaveAndNavigationRegression(unittest.TestCase):
    def test_dcs_repeat_focus_and_touch_hint(self):
        s=(ROOT/"tools"/"pdfcraft"/"android_interaction_patch.py").read_text()
        for marker in ("ARTCRAFT_ANDROID_DCS", "Key::D", "Key::C", "Key::S",
                       "ARTCRAFT_ANDROID_REPEAT_TOOL_KEYS", "ctx.text_edit_focused()",
                       "ARTCRAFT_ANDROID_TOUCH_HINT", "Touch: swipe to scroll"):
            self.assertIn(marker,s)
