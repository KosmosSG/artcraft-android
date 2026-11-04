"""Host-only regression checks for PDFCraft's pinned winit adapter."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from winit_v015_compat import with_ime_api


class WinitCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.mod = (
            "impl Window {\n"
            "    pub fn set_ime_purpose(&self, _purpose: ImePurpose) {}\n"
            "    // MotionAction::Scroll\n"
            "    // MotionAction::HoverMove\n"
            "}\n"
        )

    def test_restores_both_ime_apis_and_preserves_mouse(self):
        result = with_ime_api(self.mod)
        self.assertIn("pub fn reset_ime(&self)", result)
        self.assertIn("pub fn reset_ime_with_request(&self, _request_id: u64)", result)
        self.assertIn("MotionAction::Scroll", result)
        self.assertIn("MotionAction::HoverMove", result)

    def test_rejects_missing_mouse_overlay(self):
        with self.assertRaisesRegex(ValueError, "Mouse/hover"):
            with_ime_api(self.mod.replace("MotionAction::Scroll", "no-scroll"))

    def test_rejects_upstream_api_drift(self):
        with self.assertRaisesRegex(ValueError, "IME insertion anchor"):
            with_ime_api(self.mod.replace("set_ime_purpose", "changed_ime_purpose"))

    def test_rejects_double_patch(self):
        with self.assertRaisesRegex(ValueError, "already changed"):
            with_ime_api(with_ime_api(self.mod))


if __name__ == "__main__":
    unittest.main()
