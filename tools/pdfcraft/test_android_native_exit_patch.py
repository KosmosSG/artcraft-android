#!/usr/bin/env python3
"""Native winit Android Destroy / relaunch regression tests for PDFCraft only."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/pdfcraft/android_native_exit_patch.py"
SPEC = importlib.util.spec_from_file_location("pdfcraft_android_native_exit_patch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class AndroidDestroyLoopExitTests(unittest.TestCase):
    def test_pinned_backend_patch_and_idempotence(self):
        backend = (ROOT / "vendor/winit/src/platform_impl/android/mod.rs").read_text()
        patched = MODULE.patch(backend)
        self.assertNotEqual(backend, patched)
        self.assertEqual(patched, MODULE.patch(patched))
        self.assertIn("PDFCRAFT_ANDROID5_DESTROY_EXITS_NATIVE_LOOP", patched)
        self.assertIn("self.window_target.p.exit();", patched)
        self.assertIn('MainEvent::Destroy => {', patched)
        self.assertNotIn('warn!("TODO: forward onDestroy notification to application");', patched)

    def test_unknown_upstream_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "handler changed"):
            MODULE.patch("MainEvent::Destroy => { unexpected_handler(); }")

    def test_only_pdfcraft_uses_patch(self):
        builder = (ROOT / "lib/build-common.sh").read_text()
        anchor = 'python3 "$ROOT/tools/pdfcraft/android_native_exit_patch.py" "$SRC/vendor/winit"'
        self.assertEqual(builder.count(anchor), 1)
        before = builder[:builder.index(anchor)]
        self.assertIn('if [[ "$APP" == "pdfcraft"', before)
        self.assertIn('python3 "$ROOT/tools/pdfcraft/winit_v015_compat.py"', before)
        self.assertNotIn("std::process::exit(", MODULE.REPLACEMENT)
        self.assertNotIn("clearApplicationUserData", MODULE.REPLACEMENT)

if __name__ == "__main__":
    unittest.main()
