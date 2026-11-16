#!/usr/bin/env python3
"""Fail-closed source regression gates for Android.16 nested selection UI speedup."""
import argparse
import tempfile
import unittest
from pathlib import Path

from patch_v0241_android16_heavy_selection_ui import (
    MARKER, OUTLINE_FILE, OVERLAYS_FILE, MARKS_FILE, OLD_LIMIT, NEW_LIMIT,
    OLD_OVERLAY, NEW_OVERLAY, OLD_PAINT, NEW_PAINT, OLD_KEY, NEW_KEY,
    FUNC_ANCHOR, HELPER, MARKS_CLEAR_ANCHOR, MARKS_CLEAR_REPLACEMENT,
    REPLACEMENTS, patch,
)


class SelectionPatchTests(unittest.TestCase):
    def make_sources(self, root: Path):
        for filename, substitutions in REPLACEMENTS:
            p = root / filename
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("// mock pinned upstream\n" + "\n".join(old for old, _ in substitutions))

    def test_complex_group_keeps_desktop_and_export_quality(self):
        self.assertIn("OVERLAY_MAX_ANCHORS: usize = 2_048", NEW_LIMIT)
        self.assertIn("#[cfg(target_os = \"android\")]", NEW_OVERLAY)
        self.assertIn("cfg!(target_os = \"android\") && big", NEW_KEY)
        self.assertIn("marks.clear_for_complex_selection();", NEW_PAINT)
        self.assertIn("marks.paint(st, p, xf", NEW_PAINT)
        self.assertIn("pub(super) fn clear_for_complex_selection(&mut self)", MARKS_CLEAR_REPLACEMENT)
        self.assertNotIn("render_job", NEW_OVERLAY + HELPER)
        self.assertNotIn("image_mips", NEW_OVERLAY + HELPER)
        self.assertNotIn("save", NEW_OVERLAY + HELPER)

    def test_selection_cache_key_is_revision_and_ids_scoped(self):
        self.assertIn("st.uid,", HELPER)
        self.assertIn("st.revision,", HELPER)
        self.assertIn("st.selection.objects.iter().map(|id| id.0)", HELPER)
        self.assertIn("if cached_key == key", HELPER)
        self.assertIn("ctx.data_mut(|d| d.insert_temp(id, (key, big)))", HELPER)
        self.assertIn("too_many_anchors(", HELPER)
        self.assertNotIn("st.doc.clone", HELPER)
        self.assertNotIn("document_text", HELPER)

    def test_every_anchor_required_before_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.make_sources(root)
            before = (root / OUTLINE_FILE).read_text()
            (root / MARKS_FILE).write_text("unreviewed upstream marks file")
            with self.assertRaises(ValueError):
                patch(root)
            self.assertEqual(before, (root / OUTLINE_FILE).read_text())

    def test_patch_all_three_then_refuse_second_application(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.make_sources(root)
            patch(root)
            for filename, _ in REPLACEMENTS:
                self.assertIn(MARKER, (root / filename).read_text())
            self.assertIn(NEW_LIMIT, (root / OUTLINE_FILE).read_text())
            self.assertIn(HELPER, (root / OVERLAYS_FILE).read_text())
            self.assertIn(NEW_PAINT, (root / OVERLAYS_FILE).read_text())
            self.assertIn(MARKS_CLEAR_REPLACEMENT, (root / MARKS_FILE).read_text())
            with self.assertRaises(ValueError):
                patch(root)


def validate_staged(root: Path) -> None:
    outline = (root / OUTLINE_FILE).read_text()
    overlays = (root / OVERLAYS_FILE).read_text()
    marks = (root / MARKS_FILE).read_text()
    canvas = (root / "source/vectorcraft/crates/ui-egui/src/canvas.rs").read_text()
    raster = (root / "source/vectorcraft/crates/ui-egui/src/canvas/raster.rs").read_text()
    for s in (outline, overlays, marks):
        assert MARKER in s
    assert NEW_LIMIT in outline
    assert "pub(super) const OVERLAY_MAX_ANCHORS: usize = 100_000;" in outline, "desktop unchanged"
    assert NEW_OVERLAY in overlays and NEW_PAINT in overlays and HELPER in overlays
    assert NEW_KEY in overlays
    assert MARKS_CLEAR_REPLACEMENT in marks
    assert "VC_ANDROID13_HEAVY_AI" in canvas and "VC_ANDROID13_HEAVY_AI" in outline
    assert "VC_ANDROID14_INPLACE_PAN" in raster
    assert "VC_ANDROID15_ADAPTIVE_PAN" not in raster, "Android.15 must not be included"
    assert "moved_pixels_in_place(k.pixels.take()?" in raster
    assert "poll_worker(app, ui, key.doc);" in canvas and "image_mips: true" in canvas
    assert "MAX_KEPT_BYTES: usize = 64 << 20" in raster
    print("PASS: Android.16 bounded nested group UI; Android.14 baseline, cached pan, Android.13 overlays and rendering retained")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", nargs="?", type=Path)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SelectionPatchTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.builder:
        validate_staged(args.builder)
