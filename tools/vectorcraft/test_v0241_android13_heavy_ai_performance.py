#!/usr/bin/env python3
"""Fail-closed source and behavior-preservation checks for Android.13 heavy .ai."""
import argparse
import tempfile
import unittest
from pathlib import Path

from patch_v0241_android13_heavy_ai_performance import (
    APP_AFTER,
    CANVAS_AFTER,
    MARKER,
    OUTLINE_AFTER,
    REPLACEMENTS,
    patch,
)


class GuardedPatchTests(unittest.TestCase):
    def make_tree(self, root: Path):
        for name, before, _ in REPLACEMENTS:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("before\n" + before + "\nafter\n")

    def test_android_budget_preserves_desktop_and_document(self):
        self.assertIn('#[cfg(target_os = "android")]\npub(super) const OVERLAY_MAX_ANCHORS: usize = 8_000;', OUTLINE_AFTER)
        self.assertIn('#[cfg(not(target_os = "android"))]\npub(super) const OVERLAY_MAX_ANCHORS: usize = 100_000;', OUTLINE_AFTER)
        self.assertNotIn("doc.layers", OUTLINE_AFTER)
        self.assertNotIn("Document::", OUTLINE_AFTER)
        self.assertNotIn("renderer.render", OUTLINE_AFTER)

    def test_timing_is_privacy_safe_and_android_only(self):
        self.assertIn('VC_PERF_SELECTION_OVERLAY', CANVAS_AFTER)
        self.assertIn('VC_PERF_DOCKED_PANELS', APP_AFTER)
        self.assertIn('#[cfg(target_os = "android")]', CANVAS_AFTER)
        self.assertIn('#[cfg(target_os = "android")]', APP_AFTER)
        for snippet in (CANVAS_AFTER, APP_AFTER):
            self.assertNotIn("filename", snippet)
            self.assertNotIn("doc.name", snippet)
            self.assertNotIn("text.to_string", snippet)

    def test_rejects_unreviewed_upstream_without_partial_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            missing = root / REPLACEMENTS[2][0]
            missing.write_text("unexpected upstream rewrite")
            before = (root / REPLACEMENTS[0][0]).read_text()
            with self.assertRaises(ValueError):
                patch(root)
            self.assertEqual(before, (root / REPLACEMENTS[0][0]).read_text())

    def test_source_modifies_exactly_expected_three_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_tree(root)
            patch(root)
            for name, before, after in REPLACEMENTS:
                contents = (root / name).read_text()
                self.assertIn(MARKER, contents)
                self.assertEqual(contents.count(after), 1)
                if name.endswith("canvas/outline.rs"):
                    self.assertEqual(contents.count(before), 1)  # desktop cap preserved
                else:
                    self.assertNotIn(before, contents)
            with self.assertRaises(ValueError):
                patch(root)


def validate_staged(root: Path):
    for name, before, after in REPLACEMENTS:
        contents = (root / name).read_text()
        assert MARKER in contents and after in contents, name
        assert (contents.count(before) == 1 if name.endswith("canvas/outline.rs") else before not in contents), name
    # Keep upstream's cache and worker; do not replace them.
    canvas = (root / "source/vectorcraft/crates/ui-egui/src/canvas.rs").read_text()
    assert "crate::render_worker::Worker::spawn" in canvas
    assert "poll_worker(app, ui, key.doc);" in canvas
    assert "reproject_frame(app, &painter" in canvas
    assert "if big { &[] } else { &st.selection.objects }" in (
        root / "source/vectorcraft/crates/ui-egui/src/canvas/overlays.rs"
    ).read_text()
    print("PASS: Android.13 source preflight, prior background cache and bounding box behavior preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", nargs="?", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GuardedPatchTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.builder:
        validate_staged(args.builder)
