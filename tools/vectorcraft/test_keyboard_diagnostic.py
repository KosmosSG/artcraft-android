"""Test-only keyboard trace coverage: visibility, privacy and isolated identity."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java"
SHELL = ROOT / "adapters/vectorcraft/src/lib.rs"
CANDIDATE = ROOT / "tools/vectorcraft/keyboard_candidate.py"


class KeyboardDiagnosticTests(unittest.TestCase):
    def test_activity_observes_without_swallowing_keys(self):
        text = ACTIVITY.read_text()
        self.assertIn("public boolean dispatchKeyEvent(KeyEvent event)", text)
        self.assertIn("return super.dispatchKeyEvent(event);", text)
        self.assertIn("public String vcKeyboardDiagnostics()", text)
        self.assertIn("keyboardChildCount++", text)
        self.assertIn("keyboardImeCommits++", text)
        self.assertIn("event.getKeyCode()", text)
        self.assertIn("KeyEvent.keyCodeToString", text)
        # Must not emit arbitrary typed text or raw text contents into diagnostics.
        self.assertNotIn('keyboardLastKey = event.getCharacters()', text)

    def test_shell_has_visible_reserved_space_trace(self):
        text = SHELL.read_text()
        self.assertIn('struct KeyboardTrace {', text)
        self.assertIn('fn keyboard_diagnostics(&self) -> Result<String, String>', text)
        self.assertIn('jni_str!("vcKeyboardDiagnostics")', text)
        self.assertIn('Panel::bottom("vectorcraft.test.keyboard_diagnostics")', text)
        self.assertIn('self.keyboard_trace.observe(raw, true);', text)
        self.assertIn('self.keyboard_trace.observe(raw, false);', text)
        self.assertIn('apply_android_modifiers(&mut self.modifiers, raw);', text)
        self.assertIn('self.inner.raw_input_hook(raw);', text)
        self.assertIn('self.inner.session.tool_wants_text()', text)
        self.assertIn('self.inner.session.tool_id()', text)
        self.assertIn('ui.ctx().text_edit_focused()', text)
        self.assertIn('ui.ctx().request_repaint_after(', text)

    def test_diagnostic_is_isolated_from_installed_apps(self):
        text = CANDIDATE.read_text()
        self.assertIn('com.artcraft.vectorcraft.keyboarddiag', text)
        self.assertIn('VectorCraft Key Diagnostic', text)
        self.assertIn('PRODUCTION = "com.artcraft.vectorcraft"', text)


if __name__ == "__main__":
    unittest.main()
