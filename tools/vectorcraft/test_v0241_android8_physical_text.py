"""Preflight of Android.8 physical-key Event::Text routing.

Does not assert that a real device can type; tests that the source transforms
match pinned overlays and preserve both IME commits and native shortcuts.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

from patch_v0241_android7_physical_typing import patch as patch_android7
from patch_v0241_android8_physical_text import patch as patch_android8

ROOT = Path(__file__).resolve().parents[2]
JAVA = Path("adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java")
BRIDGE = Path("adapters/vectorcraft/src/ime_bridge.rs")
MODIFIERS = Path("adapters/vectorcraft/src/android_modifiers.rs")


def fixture(root: Path) -> None:
    for relative in (JAVA, BRIDGE, MODIFIERS):
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text((ROOT / relative).read_text())
    java = root / JAVA
    source = java.read_text()
    signature = "                public boolean onKeyDown(int keyCode, KeyEvent event) {"
    source = source.replace(signature,
                            signature + "\n                    if (vcStylusIntercept(event)) return true;", 1)
    source = source.replace("    private EditText imeView;",
                            "    private EditText imeView;\n    private long vcImeFocusEpoch = 0L;", 1)
    # Android.11 diagnostic and Android.12 shortcut overlays generate these
    # methods before Android.8; model their exact stable anchors in this cheap
    # isolated unit test without altering owner release sources.
    source = source.replace("    private void imeSetup() {", """    private final java.util.concurrent.atomic.AtomicLong vcTraceCommits =
        new java.util.concurrent.atomic.AtomicLong();
    private final java.util.concurrent.atomic.AtomicLong vcTraceRejected =
        new java.util.concurrent.atomic.AtomicLong();
    public boolean dispatchKeyEvent(KeyEvent event) {
        return super.dispatchKeyEvent(event);
    }
    private String vcDiagnosticSnapshotForTest() {
        return "test" + "; ime_callback_rejected=" + vcTraceRejected.get();
    }
    private void imeSetup() {""", 1)
    java.write_text(source)
    patch_android7(root)

    # Mirror the reviewed reset matcher shape. The full builder preflight
    # separately verifies the actual Android.8 source after every overlay.
    bridge = root / BRIDGE
    source = bridge.read_text()
    before = """                        if let Some(event) = translate(&event) {
                            raw.events.push(event);
                        }"""
    after = """                        if let Some(encoded) = event.strip_prefix('r') {
                            let key = egui::Id::unique(("vc-android-ime-reset", ctx.viewport_id()));
                            let matching = encoded.parse::<u64>().ok().and_then(|serial| {
                                ctx.data(|data| data.get_temp::<Option<egui::ImeResetId>>(key).flatten())
                                    .filter(|id| id.as_u64() == serial
                                        && id.viewport_id() == ctx.viewport_id())
                            });
                            if let Some(request_id) = matching {
                                raw.events.push(egui::Event::ImeResetCompleted { request_id });
                            }
                        } else if let Some(event) = translate(&event) {
                            raw.events.push(event);
                        }"""
    assert source.count(before) == 1
    bridge.write_text(source.replace(before, after, 1))


class Android8HardwareTextTests(unittest.TestCase):
    def test_application_text_separate_from_composition_and_wheel_shortcuts(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            patch_android8(root)
            java = (root / JAVA).read_text()
            bridge = (root / BRIDGE).read_text()
            modifiers = (root / MODIFIERS).read_text()
            self.assertIn('imeEvents.offer("t" + new String(Character.toChars(unicode)))', java)
            self.assertNotIn('imeEvents.offer("c" + new String(Character.toChars(unicode)))', java)
            self.assertIn('imeEvents.offer("c" + text);', java)
            self.assertIn("if (vcStylusIntercept(event)) return true;", java)
            for guard in ("!event.isCtrlPressed()", "!event.isAltPressed()",
                          "!event.isMetaPressed()", "event.getDeviceId() >= 0"):
                self.assertIn(guard, java)
            self.assertIn("'t' if !payload.is_empty() => Some(egui::Event::Text", bridge)
            self.assertIn("'c' if !payload.is_empty()", bridge)
            self.assertIn("raw.events.push(egui::Event::ImeResetCompleted { request_id })", bridge)
            self.assertIn("raw.events.push(egui::Event::ModifiersChanged(", bridge)
            self.assertIn("*state = AndroidModifiers::default();", modifiers)
            self.assertIn("egui::Event::Text(_) if state.modifiers().command => {}", modifiers)

    def test_incompatible_source_refused_without_partial_changes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            java_path = root / JAVA
            original_java = java_path.read_text()
            bridge_path = root / BRIDGE
            original_bridge = bridge_path.read_text()
            modifiers_path = root / MODIFIERS
            original_modifiers = modifiers_path.read_text()
            java_path.write_text(original_java.replace('VC_IME7 physical_text_commit',
                                                       'third_party_changed_marker'))
            with self.assertRaisesRegex(RuntimeError, "privacy-safe hardware marker"):
                patch_android8(root)
            self.assertEqual(bridge_path.read_text(), original_bridge)
            self.assertEqual(modifiers_path.read_text(), original_modifiers)

    @unittest.skipUnless(os.environ.get("VC_ANDROID8_STAGED"), "set VC_ANDROID8_STAGED to check generated production source")
    def test_full_staged_build_source(self):
        root = Path(os.environ["VC_ANDROID8_STAGED"])
        java = (root / JAVA).read_text()
        bridge = (root / BRIDGE).read_text()
        modifiers = (root / MODIFIERS).read_text()
        self.assertIn('imeEvents.offer("t" + new String(Character.toChars(unicode)))', java)
        self.assertIn('imeEvents.offer("c" + text);', java)
        self.assertIn("VC_IME8 physical_text_application", java)
        self.assertIn("'t' if !payload.is_empty() => Some(egui::Event::Text", bridge)
        self.assertIn("get_temp::<Option<egui::ImeResetId>>(key).flatten()", bridge)
        self.assertIn("egui::Event::ModifiersChanged(modifiers)", modifiers)


if __name__ == "__main__":
    unittest.main()
