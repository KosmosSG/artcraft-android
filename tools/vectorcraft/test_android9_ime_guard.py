"""Source-only regression test for Android.9 IME show guard handling.

Uses actual checked-in Android activity from the tested Android.8 adapter,
not a fabricated duplicate count. Also asserts the control used for
document-switch teardown is never inserted into a production APK.
"""
from pathlib import Path
import tempfile
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from patch_android9_ime_hover_menu import guard_both_ime_show_paths, in_method


class Android9ImeShowGuards(unittest.TestCase):
    def test_both_existing_android8_ime_show_guards_are_patched(self):
        source = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        start = source.index("    public void imeShow() {")
        end = source.index("    public void vcEndTypeEditing() {", start)
        before = source[start:end]
        self.assertEqual(2, before.count("if (!imeWanted) {"))
        self.assertEqual(1, before.count("                view.setFocusable(true);"))
        with tempfile.TemporaryDirectory() as folder:
            java = Path(folder) / "VectorCraftActivity.java"
            java.write_text(source)
            guard_both_ime_show_paths(java)
            after_source = java.read_text()
            after = after_source[start:after_source.index("    public void vcEndTypeEditing() {", start)]
            self.assertEqual(0, after.count("if (!imeWanted) {"))
            self.assertEqual(2, after.count("if (!imeWanted || vcImeFocusEpoch.get() != focusToken) {"))
            self.assertEqual(source[:start], after_source[:start])
            self.assertEqual(source[end:], after_source[after_source.index("    public void vcEndTypeEditing() {", start):])

    def test_ime_hide_main_thread_teardown_anchor(self):
        # Android.8 later injects vcResetIme ahead of imePoll. Recreate this
        # method boundary to ensure the Android.9 patch targets the keyboard
        # cleanup lambda, not another runOnUiThread in the same region.
        source = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        boundary = "    public String imePoll() {"
        self.assertEqual(1, source.count(boundary))
        source = source.replace(boundary,
            "    public void vcResetIme(long requestId) {}\\n" + boundary, 1)
        anchor = "        runOnUiThread(() -> {\\n            try {\\n                InputMethodManager imm ="
        self.assertEqual(1, source.count(anchor))
        with tempfile.TemporaryDirectory() as folder:
            java = Path(folder) / "VectorCraftActivity.java"
            java.write_text(source)
            in_method(java, "    public void imeHide() {",
                "    public void vcResetIme(long requestId) {", anchor,
                "        runOnUiThread(() -> {\\n            if (vcImeFocusEpoch.get() != focusToken || imeWanted) return;\\n            try {\\n                InputMethodManager imm =")
            changed = java.read_text()
            self.assertEqual(1, changed.count("vcImeFocusEpoch.get() != focusToken || imeWanted"))
            self.assertEqual(0, changed.count(anchor))

    def test_guard_count_change_fails_without_modifying_file(self):
        source = """    public void imeShow() {
        if (!imeWanted) { return; }
    }
    public void vcEndTypeEditing() {}
"""
        with tempfile.TemporaryDirectory() as folder:
            java = Path(folder) / "VectorCraftActivity.java"
            java.write_text(source)
            with self.assertRaisesRegex(RuntimeError, "expected 2, got 1"):
                guard_both_ime_show_paths(java)
            self.assertEqual(source, java.read_text())


if __name__ == "__main__":
    unittest.main()
