#!/usr/bin/env python3
"""Static regression guard for PDFCraft-only Android.6 lifecycle observability."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "templates/android/pdfcraft_mobile_java.txt"

class LifecycleTraceTests(unittest.TestCase):
    def test_activity_callbacks_instrumented_without_changing_exit(self):
        s = SOURCE.read_text()
        for callback in ("onPause", "onStop", "onDestroy"):
            self.assertEqual(s.count("protected void " + callback + "()"), 1)
            self.assertIn('pdfLifecycleTrace("' + callback + ':before")', s)
            self.assertIn('pdfLifecycleTrace("' + callback + ':after")', s)
        self.assertIn('android.util.Log.i("PDFCraftLifecycle"', s)
        self.assertIn("android.os.Process.myPid()", s)
        self.assertIn("finishAndRemoveTask();", s)
        self.assertNotIn("System.exit(", s)
        self.assertNotIn("clearApplicationUserData(", s)

if __name__ == "__main__":
    unittest.main()
