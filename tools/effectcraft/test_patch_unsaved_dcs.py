#!/usr/bin/env python3
"""Patch safety regression checks against the pinned upstream checkout, not an APK test."""
from pathlib import Path
import tempfile
import sys
import unittest
from patch_unsaved_dcs import apply

SOURCE = Path(sys.argv.pop(1)).joinpath("crates/ui-egui/src/panels/unsaved.rs").read_bytes()
REL = Path("crates/ui-egui/src/panels/unsaved.rs")

class PatchSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / REL
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(SOURCE)

    def test_reapplication_refuses_without_changing_patched_source(self):
        apply(self.root)
        patched = self.target.read_bytes()
        with self.assertRaises(RuntimeError):
            apply(self.root)
        self.assertEqual(self.target.read_bytes(), patched)

    def test_late_anchor_drift_leaves_original_bytes_untouched(self):
        # The Escape anchor is last: earlier substitutions must not leak to disk.
        drifted = SOURCE.replace(b"ctx.input(|i| i.key_pressed(egui::Key::Escape))",
                                 b"ctx.input(|i| i.key_down(egui::Key::Escape))")
        self.assertNotEqual(drifted, SOURCE)
        self.target.write_bytes(drifted)
        with self.assertRaises(RuntimeError):
            apply(self.root)
        self.assertEqual(self.target.read_bytes(), drifted)

    def test_duplicate_anchor_refuses_without_writing(self):
        duplicated = SOURCE + b'\nlet r = ui.button(tr("Don\'t Save"));\n'
        self.target.write_bytes(duplicated)
        with self.assertRaises(RuntimeError):
            apply(self.root)
        self.assertEqual(self.target.read_bytes(), duplicated)

    def test_command_execution_and_existing_upstream_tests_preserved(self):
        apply(self.root)
        patched = self.target.read_text()
        original = SOURCE.decode()
        marker = "fn answer_with("
        self.assertEqual(patched[patched.index(marker):], original[original.index(marker):])
        self.assertIn("if answer.is_none() && !revert {", patched)
        self.assertIn('("  Revert  ", "dialog.unsaved.revert")', patched)

if __name__ == "__main__":
    unittest.main()
