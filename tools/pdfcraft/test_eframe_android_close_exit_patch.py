#!/usr/bin/env python3
"""Tests for PDFCraft-only Android6 explicit eframe native-loop termination."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "pdfcraft_android6_eframe_exit_patch",
    ROOT / "tools/pdfcraft/eframe_android_close_exit_patch.py"
)
assert SPEC and SPEC.loader
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

class EframeNativeQuitTests(unittest.TestCase):
    def test_close_requests_event_loop_exit_after_save(self):
        sample = PATCH.OLD + "\n        if exit { event_loop.exit(); }\n"
        updated = PATCH.patch(sample)
        self.assertIn("PDFCRAFT_ANDROID6_EFRAME_CLOSE_EXITS_LOOP", updated)
        self.assertEqual(PATCH.patch(updated), updated)
        self.assertLess(updated.index("self.winit_app.save_and_destroy();"),
                        updated.index("exit = true;"))
        self.assertIn("#[cfg(target_os = \"android\")]", updated)
        self.assertIn("event_loop.exit();", updated)
    def test_fail_closed_on_drift(self):
        with self.assertRaises(ValueError):
            PATCH.patch("EventResult::CloseRequested => { /* drift */ }\nif exit { event_loop.exit(); }")
        with self.assertRaises(ValueError):
            PATCH.patch(PATCH.OLD)
    def test_scoped_to_disposable_pdfcraft_build(self):
        builder = (ROOT / "lib/build-common.sh").read_text()
        self.assertIn('if [[ "$APP" == "pdfcraft" && "${PDFCRAFT_ANDROID6_EFRAME_CLOSE_EXIT:-0}" == "1" ]]; then', builder)
        self.assertIn('tools/pdfcraft/eframe_android_close_exit_patch.py', builder)
        self.assertEqual(PATCH.PINNED, "6d518fc799681571963842f95b55a6b68431b15a")
        self.assertNotIn("std::process::exit(", PATCH.NEW)

if __name__ == "__main__":
    unittest.main()
