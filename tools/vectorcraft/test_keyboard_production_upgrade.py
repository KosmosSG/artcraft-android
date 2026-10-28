"""Regression gates for promoting the owner-tested keyboard behavior onto VectorCraft production .8.

These are structural checks; the GitHub workflow also compiles the actual ARM64 APK,
verifies package/version/certificate against released .8, and retains a signed candidate.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class KeyboardProductionUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = (ROOT / "adapters/vectorcraft/src/lib.rs").read_text()
        cls.modifiers = (ROOT / "adapters/vectorcraft/src/android_modifiers.rs").read_text()
        cls.java = (ROOT / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        cls.manifest = (ROOT / "adapters/vectorcraft/Cargo.toml").read_text()

    def test_production_package_and_original_features_remain(self):
        self.assertIn('package = "com.artcraft.vectorcraft"', self.manifest)
        self.assertNotIn("com.artcraft.vectorcraft.keyboardtest", self.manifest)
        for feature in ("FontUiState", "check_for_updates", "system_fonts", "startup_updates",
                        "persist_save(", "persist_load(", "ARTCRAFT_VECTORCRAFT_SAF_BRIDGE_V1",
                        "import_status", "shared_status", "VectorCraftExtras"):
            with self.subTest(feature=feature):
                self.assertIn(feature, self.shell + self.java)
        self.assertIn('vectorcraft-tools = { path = "../../crates/tools" }', self.manifest)

    def test_keyboard_escape_tool_and_context_bar_guards(self):
        for marker in ("CanvasHardwareCommand::ExitType", "CanvasHardwareCommand::PreserveContextBar",
                       "ctx.text_edit_focused()", "tool_wants_text()", "tool_composing()",
                       "self.inner.ui.dialog.is_some()", "memory.surrender_focus(id)",
                       "self.inner.session.tool_busy()", "self.inner.select_tool(tool)",
                       "UiRequest::SwitchTool", "consume_canvas_hardware_command(raw, command)",
                       "restore_tool_key_text(raw, allow_letters)"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.shell)
        self.assertNotIn("self.inner.ui.task_bar = false;", self.shell)
        for marker in ("escape_preserves_context_bar_and_tool_shortcuts",
                       "type_shortcut_returns_after_escape_exits_editor",
                       "direct_tool_dispatch_consumes_only_matching_letter_events",
                       "fn escape_is_routed_during_type_editing_without_stealing_ime",
                       "if field_focused || composing || modal_open"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.modifiers)

    def test_native_escape_restores_focus_but_does_not_steal_input(self):
        for marker in ("fn end_type_editing(&self)", 'jni_str!("vcEndTypeEditing")',
                       "self.bridge.end_type_editing()"):
            self.assertIn(marker, self.shell)
        for marker in ("public void vcEndTypeEditing()", "imeWanted = false;",
                       "view.clearFocus();", "child.requestFocus()", "imeEvents.clear();"):
            self.assertIn(marker, self.java)
        self.assertIn("return false;", self.java)  # invisible EditText hardware event passthrough
        self.assertIn("imePoll()", self.java)

    def test_release_version_and_key_not_contaminated(self):
        self.assertNotIn("TEST_VERSION_CODE", self.manifest)
        self.assertIn('name = "vectorcraft-android"', self.manifest)
        self.assertNotIn("keytool -genkey", self.shell)
        self.assertNotIn("gh release", self.shell)


if __name__ == "__main__":
    unittest.main()
