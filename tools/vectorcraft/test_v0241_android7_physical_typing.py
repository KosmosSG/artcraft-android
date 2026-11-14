"""Regression tests for the Android.7 post-stylus physical typing patch.

Exercise the exact earlier wheel-interceptor insertion that caused run
43551081211 to fail, without touching a real document or release APK.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from patch_v0241_android7_physical_typing import patch

ROOT = Path(__file__).resolve().parents[2]
JAVA_REL = Path("adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java")
HANDLER = "                public boolean onKeyDown(int keyCode, KeyEvent event) {"
STYLUS = "                    if (vcStylusIntercept(event)) return true;"


def fixture(root: Path, *, with_stylus: bool) -> Path:
    raw = (ROOT / JAVA_REL).read_text()
    assert raw.count(HANDLER) == 1
    assert STYLUS not in raw
    if with_stylus:
        raw = raw.replace(HANDLER, HANDLER + "\n" + STYLUS, 1)
    # Android.9 supplies the focus-epoch fence ahead of the Android.7 patch.
    assert "vcImeFocusEpoch" not in raw
    raw = raw.replace("    private EditText imeView;",
                      "    private EditText imeView;\n    private long vcImeFocusEpoch = 0L;", 1)
    target = root / JAVA_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(raw)
    return target


class PhysicalTypingPatchTests(unittest.TestCase):
    def test_patch_after_stylus_preserves_native_and_ime_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            java = fixture(root, with_stylus=True)
            before = java.read_text()
            patch(root)
            after = java.read_text()
            self.assertEqual(after.count(STYLUS), 1)
            self.assertEqual(after.count("VC_IME7 physical_text_commit"), 1)
            self.assertLess(after.index(STYLUS), after.index("VC_IME7 physical_text_commit"))
            self.assertIn('imeEvents.offer("c" + new String(Character.toChars(unicode)))', after)
            self.assertIn("!event.isCtrlPressed()", after)
            self.assertIn("!event.isAltPressed()", after)
            self.assertIn("!event.isMetaPressed()", after)
            self.assertIn('imeEvents.offer("c" + text);', after)
            self.assertIn("vcImeFocusEpoch", after)
            self.assertEqual(after.count("onKeyUp(int keyCode, KeyEvent event)"),
                             before.count("onKeyUp(int keyCode, KeyEvent event)"))

    def test_additional_preexisting_handler_guard_remains(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            java = fixture(root, with_stylus=True)
            existing = "                    if (event.getRepeatCount() == -99) return true;"
            source = java.read_text().replace(STYLUS, STYLUS + "\n" + existing, 1)
            java.write_text(source)
            patch(root)
            output = java.read_text()
            self.assertEqual(output.count(existing), 1)
            self.assertLess(output.index(existing), output.index("VC_IME7 physical_text_commit"))

    def test_absent_stylus_anchor_is_rejected_without_mutation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            java = fixture(root, with_stylus=False)
            before = java.read_text()
            with self.assertRaisesRegex(RuntimeError, "post-stylus physical text path changed"):
                patch(root)
            self.assertEqual(java.read_text(), before)

    def test_second_application_is_rejected_without_mutation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            java = fixture(root, with_stylus=True)
            patch(root)
            before = java.read_text()
            with self.assertRaisesRegex(RuntimeError, "post-stylus physical text path changed"):
                patch(root)
            self.assertEqual(java.read_text(), before)


if __name__ == "__main__":
    unittest.main()
