"""Regression guards: native MotionEvent file recording + SAF export, EffectCraft only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from patch_android_local_diag import (
    apply_native, apply_java, NATIVE, JAVA, NATIVE_ANCHOR, JAVA_CLASS,
    JAVA_ON_RESULT, JAVA_ON_CREATE,
)

class AppLocalMotionDiagnosis(unittest.TestCase):
    def test_native_events_recorded_without_logcat(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            file = root / NATIVE
            file.parent.mkdir(parents=True)
            file.write_text(
                "fn main() { MotionAction::Scroll => { }\n"
                "MotionAction::Move if pointer_class { }\n"
                "Axis::__Unknown(50); Axis::__Unknown(52);\n"
                + NATIVE_ANCHOR + "\n}\n"
            )
            apply_native(root)
            code = file.read_text()
            self.assertIn("EC11 time_ms=", code)
            self.assertIn('OpenOptions::new()', code)
            self.assertIn("android_app.internal_data_path()", code)
            self.assertIn("Axis::__Unknown(48)", code)
            self.assertIn("Axis::__Unknown(49)", code)
            self.assertIn("Axis::__Unknown(50)", code)
            self.assertIn("Axis::__Unknown(51)", code)
            self.assertIn("Axis::__Unknown(52)", code)
            self.assertIn("MotionAction::Scroll", code)
            self.assertIn("std::time::SystemTime", code)
            self.assertNotIn("device_id()", code)
            self.assertNotIn("pointer.x()", code)
            self.assertNotIn("pointer.y()", code)
            self.assertIn("match motion_event.action()", code)
            with self.assertRaisesRegex(RuntimeError, "applied twice"):
                apply_native(root)

    def test_export_via_android_picker_without_root_or_logcat(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            file = root / JAVA
            file.parent.mkdir(parents=True)
            file.write_text(JAVA_CLASS + "\n" +
                "    void onCreate(){\n" + JAVA_ON_CREATE + "\n}\n" +
                "    void onActivityResult(){\n" + JAVA_ON_RESULT + "\n}\n}")
            apply_java(root)
            code = file.read_text()
            self.assertIn("public void ec11RequestExport()", code)
            self.assertIn("ACTION_CREATE_DOCUMENT", code)
            self.assertIn("EC11_EXPORT_REQ", code)
            self.assertIn("getFilesDir()", code)
            self.assertIn("runOnUiThread(() -> {", code)
            self.assertNotIn("ec11SetupExportButton();", code)
            self.assertIn("ec11ExportResult(resultCode, data);", code)
            self.assertIn("EC11_DIAG_NO_NATIVE_FILE", code)
            self.assertNotIn("addContentView(button, params);", code)
            self.assertIn("super.onActivityResult(requestCode, resultCode, data);", code)
            with self.assertRaisesRegex(RuntimeError, "applied twice"):
                apply_java(root)

    def test_drift_guard_does_not_partially_modify(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            file = root / JAVA
            file.parent.mkdir(parents=True)
            file.write_text(JAVA_CLASS + "\n")
            original=file.read_text()
            with self.assertRaisesRegex(RuntimeError, "drift"):
                apply_java(root)
            self.assertEqual(file.read_text(), original)

if __name__ == "__main__":
    unittest.main()
