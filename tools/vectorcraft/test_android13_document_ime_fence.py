"""Android.13 source/behavioral regression gates for document-IME handoff.

A queue-model checks the ordered fence contract; generated-source assertions
verify the Java/Rust integration without claiming on-device IME verification.
"""
import os
import unittest
from pathlib import Path

from patch_android13_document_ime_fence import replace_exact


def retain_control_events_after_doc_switch(events):
    """Model Java's document-switch removal rule; never interpret payloads."""
    return [event for event in events if event.startswith("r")]


def match_completed_reset(events, outstanding):
    """Model the Rust exact-id matcher: mismatched completions are rejected."""
    accepted = []
    for event in events:
        if event.startswith("r") and event[1:].isdigit() and int(event[1:]) == outstanding:
            accepted.append(int(event[1:]))
    return accepted


class DocumentImeFenceTests(unittest.TestCase):
    def test_document_change_keeps_reset_controls_but_not_old_text(self):
        events = ["c" + "old", "p" + "old", "r100", "f", "r101", "d1,0"]
        kept = retain_control_events_after_doc_switch(events)
        self.assertEqual(kept, ["r100", "r101"])
        self.assertEqual(match_completed_reset(kept, 101), [101])
        self.assertEqual(match_completed_reset(kept, 102), [])
        self.assertEqual(match_completed_reset(kept, 100), [100])

    def test_successive_document_closures_do_not_lose_matching_ack(self):
        events = ["r8", "c" + "ab", "r9"]
        first = retain_control_events_after_doc_switch(events)
        second = retain_control_events_after_doc_switch(first + ["p" + "new", "r10"])
        self.assertEqual(second, ["r8", "r9", "r10"])
        self.assertEqual(match_completed_reset(second, 10), [10])
        self.assertFalse(match_completed_reset(second, 11))

    def test_guarded_anchor_rejects_absent_or_duplicate_source(self):
        with self.assertRaises(ValueError):
            replace_exact("other", "missing", "new", "test")
        with self.assertRaises(ValueError):
            replace_exact("anchor anchor", "anchor", "new", "test")
        self.assertEqual(replace_exact("a OLD b", "OLD", "NEW", "test"), "a NEW b")

    @unittest.skipUnless(os.environ.get("VC_ANDROID13_STAGED"), "requires generated adapter")
    def test_generated_java_native_reset_handshake(self):
        root = Path(os.environ["VC_ANDROID13_STAGED"])
        java = (root / "adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
        rust = (root / "adapters/vectorcraft/src/lib.rs").read_text()
        bridge = (root / "adapters/vectorcraft/src/ime_bridge.rs").read_text()
        engine = (root / "source/vectorcraft/crates/ui-egui/src/ime.rs").read_text()
        a = java.index("    public void vcDocumentChanged() {")
        b = java.index("    public boolean vcStylusHoverActive() {", a)
        document_change = java[a:b]
        self.assertIn('imeEvents.removeIf(event -> !event.startsWith("r"));', document_change)
        self.assertNotIn("imeEvents.clear();", document_change)
        self.assertIn("vcImeNeedsRebind = true;", document_change)
        self.assertIn("vcImeFocusEpoch.incrementAndGet()", document_change)
        self.assertIn("VC_IME13 document_switch preserved_reset_controls", document_change)
        self.assertIn("private volatile boolean vcImeNeedsRebind = true;", java)
        self.assertIn("connectionGeneration != vcImeGeneration", java)
        self.assertIn("vcImeResetting || connectionGeneration != vcImeGeneration", java)
        self.assertIn('event.strip_prefix(\'r\')', bridge)
        self.assertIn("id.as_u64() == serial", bridge)
        self.assertIn("id.viewport_id() == ctx.viewport_id()", bridge)
        self.assertIn("raw.events.push(egui::Event::ImeResetCompleted { request_id });", bridge)
        self.assertIn("guard.request == Some(request)", engine)
        self.assertIn("guard.destination == destination", engine)
        self.assertIn("guard.context == crate::graphics::context_tag(ctx)", engine)
        self.assertIn("self.bridge.vc_document_changed()", rust)
        self.assertNotIn('ctx.data_mut(|data| data.remove_temp::<Option<egui::ImeResetId>>(reset_key));', rust)
        self.assertIn("self.ime.poll(ctx, raw)", rust)
        self.assertIn("finish_android_after_quit", rust)
        self.assertIn("vcMarkNativeQuitStage", java)
        self.assertNotIn("System.exit(", java)
        self.assertNotIn("killProcess(", java)


if __name__ == "__main__":
    unittest.main()
