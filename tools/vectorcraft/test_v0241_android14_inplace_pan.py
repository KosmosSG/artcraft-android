#!/usr/bin/env python3
"""Fail-closed checks for VectorCraft Android.14 cached-frame RGBA buffer reuse."""
import argparse
import tempfile
import unittest
from pathlib import Path

from patch_v0241_android14_inplace_pan import (
    AFTER_COPY, ANCHOR_COPY, ANCHOR_FUNC, FAST, MARKER, patch
)

RASTER = "source/vectorcraft/crates/ui-egui/src/canvas/raster.rs"


class PanPatchTests(unittest.TestCase):
    def test_source_changes_only_previous_frame_ownership(self):
        self.assertIn("#[cfg(target_os = \"android\")]", AFTER_COPY)
        self.assertIn("k.pixels.take()?", AFTER_COPY)
        self.assertIn("#[cfg(not(target_os = \"android\"))]", AFTER_COPY)
        self.assertIn("moved_pixels(k.pixels.as_ref()?", AFTER_COPY)
        self.assertIn("copy_within(", FAST)
        self.assertIn("#[cfg(any(target_os = \"android\", test))]", FAST)
        self.assertIn("moved_pixels(&src,", FAST)
        self.assertIn("moved_pixels_in_place(src.clone()", FAST)
        self.assertNotIn("set_image_cache_budget", AFTER_COPY + FAST)
        self.assertNotIn("MAX_KEPT_BYTES =", AFTER_COPY + FAST)

    def test_exact_anchors_are_required_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / RASTER
            path.parent.mkdir(parents=True)
            path.write_text("header\n" + ANCHOR_FUNC + "\n" + ANCHOR_COPY + "\nfooter\n")
            patch(Path(d))
            s = path.read_text()
            self.assertIn(MARKER, s)
            self.assertIn(FAST, s)
            self.assertIn(AFTER_COPY, s)
            self.assertNotIn(ANCHOR_COPY, s)
            with self.assertRaises(ValueError):
                patch(Path(d))
            self.assertEqual(s, path.read_text())

    def test_mismatched_source_is_never_changed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / RASTER
            path.parent.mkdir(parents=True)
            path.write_text("unreviewed source\n" + ANCHOR_FUNC)
            with self.assertRaises(ValueError):
                patch(Path(d))
            self.assertEqual("unreviewed source\n" + ANCHOR_FUNC, path.read_text())


def validate_staged(builder: Path):
    raster = (builder / RASTER).read_text()
    assert raster.count("VC_ANDROID14_INPLACE_PAN") >= 2
    assert raster.count(AFTER_COPY) == 1
    assert raster.count(FAST) == 1
    assert "fn moved_pixels(pixels: &[u8]," in raster, "original byte-for-byte reference retained"
    assert "fn android14_inplace_pan_matches_original_pixels_in_every_direction()" in raster
    assert "let copied = kept.as_ref().and_then" not in raster
    assert "fn render_job(" not in raster or "pub(crate) fn render_job(" in raster
    canvas = (builder / "source/vectorcraft/crates/ui-egui/src/canvas.rs").read_text()
    outline = (builder / "source/vectorcraft/crates/ui-egui/src/canvas/outline.rs").read_text()
    assert "VC_ANDROID13_HEAVY_AI" in canvas and "VC_ANDROID13_HEAVY_AI" in outline
    assert "poll_worker(app, ui, key.doc)" in canvas
    assert "reproject_frame(app, &painter" in canvas
    assert "image_mips: true" in canvas
    print("PASS: Android.14 scoped in-place pixel reuse, Android.13 overlay optimization and worker/mips preserved")


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("builder", type=Path, nargs="?")
    args = arg.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(PanPatchTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.builder:
        validate_staged(args.builder)
