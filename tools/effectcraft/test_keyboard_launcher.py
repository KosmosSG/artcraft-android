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
        # This fixture includes only anchors needed by the real EffectCraft patch;
        # it is not used in any APK or production Java template.
        ime_anchors = ("    public void imeShow() {\\n"
                       "                        public boolean commitText(CharSequence text, int newCursorPosition) {\\n"
                       "                        public boolean setComposingText(CharSequence text, int newCursorPosition) {\\n"
                       "                        public boolean deleteSurroundingText(int beforeLength, int afterLength) {\\n"
                       "                        public boolean sendKeyEvent(KeyEvent event) {\\n")
        scope = {"once": once, "j": "public final class __CLASS__ extends " + base + " {\\nvoid imeHide(){\\n                view.clearFocus();\\n}\\n" + ime_anchors + "}"+ suffix}
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
                self.assertIn("ecPollPhysicalShortcut()", java)
                self.assertIn("ecConsumePhysicalShortcut(event)", java)
                self.assertIn("ecConsumeDialogKey(event)", java)
                self.assertIn("imeHide();", java)

                if base == "NativeActivity":
                    self.assertNotIn("super.onKeyDown", java)
                    self.assertNotIn("super.onKeyUp", java)
                    self.assertIn("android.app.NativeActivity$NativeContentView", java)
                else:
                    self.assertIn("super.onKeyDown", java)
                    self.assertIn("super.onKeyUp", java)


    def test_unknown_or_already_patched_activity_stops(self):
        with self.assertRaises(SystemExit): self.patch("UnexpectedActivity")
        with self.assertRaises(SystemExit): self.patch("GameActivity", "boolean dispatchKeyEvent(")
