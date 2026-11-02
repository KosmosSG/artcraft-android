"""Fail-closed tests for EffectCraft v0.20 pinned Android winit input rebasing."""
from pathlib import Path
import tempfile
import unittest

from v020_winit_compat import apply, OLD_IMPORT, PINNED_IMPORT, HELPER_START, HELPER_END, START, END


class PinnedWinitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.local = self.root / "old.rs"
        self.new = self.root / "new.rs"

    def sources(self, *, old_motion=None, new_motion=None, new_ime=True):
        old_motion = old_motion or 'let pointer_class = true;\n                let wheel = MouseWheel; let click = MouseInput;\n'
        new_motion = new_motion or '// None // TODO mouse events\n'
        old = OLD_IMPORT + "\n" + HELPER_START + "\nconst MAX_LINE_SCROLL: f32 = 3.0;\nfn android_mouse_button() {}\n" + HELPER_END + "\n" + START + "\n" + old_motion + "            },\n" + END + "\n// keep keyboard\n"
        new = PINNED_IMPORT + "\n" + HELPER_END + "\nfn reset_ime_with_request() {}\n" * int(new_ime) + START + "\n" + new_motion + "            },\n" + END + "\n// official keyboard untouched\n"
        self.local.write_text(old)
        self.new.write_text(new)

    def test_merges_mouse_features_and_preserves_official_keyboard_ime(self):
        self.sources()
        apply(self.local, self.new)
        merged = self.new.read_text()
        self.assertIn("reset_ime_with_request", merged)
        self.assertIn("// official keyboard untouched", merged)
        self.assertIn("pointer_class", merged)
        self.assertIn("MouseWheel", merged)
        self.assertIn("MouseInput", merged)
        self.assertIn("fn android_mouse_button()", merged)
        self.assertIn("MAX_LINE_SCROLL", merged)
        self.assertNotIn("TODO mouse events", merged)
        self.assertEqual(merged.count(END), 1)

    def test_missing_upstream_ime_rejected_without_writing(self):
        self.sources(new_ime=False)
        before = self.new.read_text()
        with self.assertRaisesRegex(RuntimeError, "IME reset"):
            apply(self.local, self.new)
        self.assertEqual(before, self.new.read_text())

    def test_changed_upstream_motion_rejected_without_writing(self):
        self.sources(new_motion="// upstream now handles scroll\n")
        before = self.new.read_text()
        with self.assertRaisesRegex(RuntimeError, "motion handling changed"):
            apply(self.local, self.new)
        self.assertEqual(before, self.new.read_text())

    def test_missing_existing_pointer_support_rejected(self):
        self.sources(old_motion="let pointer_class = true;\n")
        with self.assertRaisesRegex(RuntimeError, "features missing"):
            apply(self.local, self.new)

    def test_second_patch_fails_closed(self):
        self.sources()
        apply(self.local, self.new)
        with self.assertRaises(RuntimeError):
            apply(self.local, self.new)


if __name__ == "__main__":
    unittest.main()
