"""Offline regression checks for official v0.20 IME API backport."""
import unittest
from patch_android_winit_ime_v020 import (
    EVENT_BEFORE, WINDOW_BEFORE, ANDROID_BEFORE, patch_sources,
)


class WinitImeCompatibilityTests(unittest.TestCase):
    def original(self):
        return (
            "pub enum WindowEvent {\n" + EVENT_BEFORE + "\n}\n",
            "impl Window {\n" + WINDOW_BEFORE + "\n}\n",
            "impl Window {\n" + ANDROID_BEFORE + "\n}\n",
        )

    def test_source_api_added_to_expected_files(self):
        event, window, android = patch_sources(*self.original())
        self.assertEqual(event.count("ImeResetCompleted { request_id: u64 }"), 1)
        self.assertEqual(window.count("pub fn reset_ime_with_request(&self, request_id: u64)"), 1)
        self.assertIn("pub fn reset_ime(&self)", window)
        self.assertEqual(android.count("pub fn reset_ime_with_request(&self, _request_id: u64)"), 1)
        self.assertIn("pub fn reset_ime(&self) {}", android)
        self.assertNotIn("WindowEvent::ImeResetCompleted", android)
        self.assertNotIn("callback(", android)

    def test_rejects_duplicate_patching(self):
        with self.assertRaises(ValueError):
            patch_sources(*patch_sources(*self.original()))

    def test_rejects_unknown_winit_base(self):
        event, window, android = self.original()
        with self.assertRaises(ValueError):
            patch_sources(event, window.replace(WINDOW_BEFORE, "// upstream changed"), android)

    def test_existing_touch_backend_unchanged_outside_anchor(self):
        event, window, android = self.original()
        android += "\n// touchpad-scroll-and-pinch-handler\n"
        patched = patch_sources(event, window, android)
        self.assertTrue(patched[2].endswith("// touchpad-scroll-and-pinch-handler\n"))


if __name__ == "__main__":
    unittest.main()
