from pathlib import Path
import unittest
from activity_history_patch import patch
ROOT = Path(__file__).resolve().parents[2]
class HistoryPatch(unittest.TestCase):
    def test_native_activity_borrowed_history_and_idempotence(self):
        source = (ROOT/'vendor/android-activity/src/native_activity/input.rs').read_text()
        result = patch(source)
        self.assertEqual(result, patch(result))
        self.assertEqual(result.count('pub fn pdfcraft_history('), 1)
        self.assertIn('self.ndk_event.history()', result)
        self.assertNotIn('pub fn pdfcraft_history(', source)
    def test_source_drift_fails_closed(self):
        with self.assertRaises(AssertionError): patch('changed API')
