"""Regression coverage for Android key-only tool shortcut fallback.

The official typed-text path, IME and text editor must remain authoritative.
"""
import tempfile
import unittest
from pathlib import Path
from android_tool_key_fallback import patch, ANCHOR, INJECTION


STUB = '''pub fn handle() {
    let typing = ctx.egui_wants_keyboard_input();
    if typing { return; }
    if app.session.tool_wants_text() { return; }
    if composing || app.session.tool_composing() { return; }
    let _ = crate::shortcut_editor::tool_for_key;
    let _ = crate::shortcut_editor::command_for_key;
    let events: Vec<(String, Modifiers)> = vec![];
    for (text, m) in events {
        println!("{text} {m:?}");
    }
}
fn letter_of(k: Key) -> Option<char> { None }
'''


class AndroidToolKeyFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "crates/ui-egui/src/shortcuts.rs"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(STUB)

    def test_only_inserts_android_specific_key_fallback(self):
        patch(Path(self.tmp.name))
        result = self.source.read_text()
        self.assertEqual(result.count(ANCHOR), 1)
        self.assertIn(INJECTION, result)
        self.assertIn('#[cfg(target_os = "android")]', result)
        self.assertIn("egui::Event::Key {", result)
        self.assertIn("pressed: true, repeat: false", result)
        self.assertIn("egui::Event::Text(_) | egui::Event::Ime(_)", result)
        self.assertIn("modifiers.command || modifiers.ctrl || modifiers.alt", result)
        self.assertIn("letter_of(physical_key.unwrap_or(*key))", result)
        self.assertIn("crate::shortcut_editor::tool_for_key", result)
        self.assertIn("crate::shortcut_editor::command_for_key", result)

    def test_patch_is_fail_closed_for_missing_anchor_and_double_application(self):
        patch(Path(self.tmp.name))
        with self.assertRaises(ValueError):
            patch(Path(self.tmp.name))
        self.source.write_text(STUB.replace(ANCHOR, "    // changed upstream\n"))
        with self.assertRaises(ValueError):
            patch(Path(self.tmp.name))

    def test_patch_refuses_removed_keyboard_safety_guards(self):
        for marker in (
            "let typing = ctx.egui_wants_keyboard_input();",
            "if typing {",
            "if app.session.tool_wants_text() {",
            "if composing || app.session.tool_composing() {",
            "crate::shortcut_editor::tool_for_key",
            "crate::shortcut_editor::command_for_key",
        ):
            with self.subTest(marker=marker):
                self.source.write_text(STUB.replace(marker, ""))
                with self.assertRaises(ValueError):
                    patch(Path(self.tmp.name))


if __name__ == "__main__":
    unittest.main()
