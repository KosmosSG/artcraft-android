"""Exercise the real Java overlay for both supported Android builder templates."""
from pathlib import Path
import unittest

class KeyboardLauncher(unittest.TestCase):
    def patch(self, base, suffix=""):
        source = Path(__file__).with_name("integrate_updater.py").read_text()
        section = "declarations = " + source.split("declarations = ", 1)[1].split("# This temporary template is used solely", 1)[0]
        def once(text, old, new, label):
            if text.count(old) != 1: raise SystemExit(label)
            return text.replace(old, new, 1)
        scope = {"once": once, "j": "public final class __CLASS__ extends " + base + " {\nvoid imeHide(){\n                view.clearFocus();\n}\n}" + suffix}
        exec(section, scope)
        return scope["j"]

    def test_native_and_game_activity_keep_their_base_and_keys(self):
        for base in ("NativeActivity", "GameActivity"):
            with self.subTest(base=base):
                java = self.patch(base)
                self.assertIn("extends " + base, java)
                self.assertEqual(java.count("boolean dispatchKeyEvent("), 1)
                self.assertIn("event.hasNoModifiers()", java)
                self.assertIn("event.getRepeatCount() == 0", java)
                self.assertIn("return super.dispatchKeyEvent(event);", java)
                self.assertIn("surface.requestFocus()", java)

    def test_unknown_or_already_patched_activity_stops(self):
        with self.assertRaises(SystemExit): self.patch("UnexpectedActivity")
        with self.assertRaises(SystemExit): self.patch("GameActivity", "boolean dispatchKeyEvent(")
