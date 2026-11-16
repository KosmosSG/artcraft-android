#!/usr/bin/env python3
"""Cheap, fail-closed Android.15 scoped renderer/source tests before ARM64 build."""
import argparse
from pathlib import Path
import tempfile
import unittest

from patch_v0241_android15_adaptive_pan_tiles import (
    ANCHOR_HELPER, MARKER, ORIGINAL_SPAN, PROFILE_END_OLD, PROFILE_END_NEW,
    PROFILE_START_OLD, PROFILE_START_NEW, SPAN_HELPER, SPAN_REPLACEMENT, patch,
)

RASTER = "source/vectorcraft/crates/ui-egui/src/canvas/raster.rs"

def simulated_span(d, n):
    length = min(abs(d), n)
    a, b = (0, length) if d > 0 else (n-length, n)
    def in_steps(a, b, n, chunks):
        step = max(1, (n+chunks-1)//chunks)
        amount = min(n, ((max(1,b-a)+step-1)//step)*step)
        start = min(a,n-amount)
        return start,start+amount
    return in_steps(a,b,n,16 if length <= max(1,(n+7)//8) else 8)

class Android15Tests(unittest.TestCase):
    def make_stub(self, d):
        target = Path(d) / RASTER
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join([
            "// VC_ANDROID14_INPLACE_PAN",
            "// VC_ANDROID14_INPLACE_PAN",
            "fn in_steps(a: u32, b: u32, n: u32) -> (u32, u32) { (a, b.min(n)) }",
            ANCHOR_HELPER,
            ORIGINAL_SPAN,
            PROFILE_START_OLD,
            PROFILE_END_OLD,
        ]))
        return target

    def test_reduced_strip_always_covers_new_area(self):
        for size in [1,2,3,7,15,31,32,33,63,128,256,720,1080,1440,2048,4096,8192]:
            for length in [1,2,3,5,7,16,31,63,127,128,255,size]:
                for d in (length,-length):
                    a,b=simulated_span(d,size)
                    x,y=(0,min(length,size)) if d>0 else (size-min(length,size),size)
                    self.assertTrue(0<=a<=x and y<=b<=size,(size,d,a,b))
            if size>=720:
                a,b=simulated_span(1,size)
                self.assertLess(b-a,(size+7)//8)

    def test_patched_source_preserves_prior_budget_and_worker(self):
        self.assertIn("#[cfg(target_os = \"android\")]", SPAN_REPLACEMENT)
        self.assertIn("#[cfg(not(target_os = \"android\"))]", SPAN_REPLACEMENT)
        self.assertIn("#[cfg(test)]", SPAN_HELPER)
        self.assertIn("render_job", PROFILE_START_NEW)
        self.assertIn("u64::from(job.w) * u64::from(job.h)", PROFILE_END_NEW)
        self.assertNotIn("filename", PROFILE_END_NEW)
        self.assertNotIn("text_content", PROFILE_END_NEW)
        self.assertNotIn("MAX_KEPT_BYTES =", SPAN_HELPER)
        self.assertNotIn("export", SPAN_REPLACEMENT.lower())
        self.assertIn("VC_ANDROID15_RENDER_JOB", PROFILE_END_NEW)

    def test_exact_source_anchors_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            target=self.make_stub(d)
            patch(Path(d))
            updated=target.read_text()
            self.assertIn(MARKER,updated)
            self.assertIn(SPAN_HELPER,updated)
            self.assertIn(SPAN_REPLACEMENT,updated)
            self.assertIn(PROFILE_START_NEW,updated)
            self.assertIn(PROFILE_END_NEW,updated)
            self.assertNotIn(ORIGINAL_SPAN,updated)
            with self.assertRaises(ValueError):
                patch(Path(d))
            self.assertEqual(updated,target.read_text())

    def test_fail_closed_when_staged_code_changed(self):
        with tempfile.TemporaryDirectory() as d:
            target=self.make_stub(d)
            contents=target.read_text().replace(PROFILE_END_OLD,"unexpected upstream output")
            target.write_text(contents)
            with self.assertRaises(ValueError):
                patch(Path(d))
            self.assertEqual(contents,target.read_text())

def check_staged(builder):
    raster=(builder / RASTER).read_text()
    canvas=(builder / "source/vectorcraft/crates/ui-egui/src/canvas.rs").read_text()
    overlays=(builder / "source/vectorcraft/crates/ui-egui/src/canvas/outline.rs").read_text()
    assert raster.count(MARKER)>=3
    assert raster.count("VC_ANDROID14_INPLACE_PAN")>=2
    assert "android15_pan_span(d, n)" in raster
    assert "android15_pan_spans_never_leave_new_pixels_blank_or_extend_past_frame" in raster
    assert "android15_small_swipes_reduce_typical_exposed_strip_pixels" in raster
    assert "moved_pixels_in_place(k.pixels.take()" in raster
    assert "fn in_steps(a: u32, b: u32, n: u32)" in raster
    assert "MAX_KEPT_BYTES: usize = 64 << 20" in raster
    assert "VC_ANDROID13_HEAVY_AI" in canvas and "VC_ANDROID13_HEAVY_AI" in overlays
    assert "image_mips: true" in canvas and "poll_worker(app, ui, key.doc);" in canvas
    print("PASS: Android.15 adaptive strips and prior Android.13/.14 cached-frame/worker/selection code preserved")

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("builder",type=Path,nargs="?")
    args=arg.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Android15Tests)
    ran=unittest.TextTestRunner(verbosity=2).run(suite)
    if not ran.wasSuccessful():
        raise SystemExit(1)
    if args.builder:
        check_staged(args.builder)
