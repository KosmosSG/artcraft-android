"""VectorCraft Android.15: smaller exposed-region redraws on short canvas pans.

The published Android.12 source and tested Android.13/14 patches stay intact.
This adds an Android-only finer quantization for exposed strips on *small*
whole-pixel pans, without changing the original pixel positions, image mips,
frame reuse, full-render fallback, exports, pen events, or texture size.
No new renderer, GPU backend or cache budget. Fail closed if the pinned
upstream and already-staged Android.14 sources differ.
"""
import argparse
from pathlib import Path

MARKER = "VC_ANDROID15_ADAPTIVE_PAN"

ORIGINAL_SPAN = """    // How much of 0..n a move by \`d\` exposes, at the start for a positive \`d\`, else at the end.
    let span = |d: i64, n: u32| {
        let len = u32::try_from(d.unsigned_abs()).ok()?.min(n);
        Some(in_steps(if d > 0 { 0 } else { n - len }, if d > 0 { len } else { n }, n))
    };"""

SPAN_REPLACEMENT = """    // VC_ANDROID15_ADAPTIVE_PAN: preserve all original pixels and offscreen
    // fallbacks. Small Android pans redraw smaller cache-aligned exposed strips;
    // large pans and other OSes keep the pinned original eighth-grid behavior.
    let span = |d: i64, n: u32| {
        #[cfg(target_os = "android")]
        {
            return Some(android15_pan_span(d, n));
        }
        #[cfg(not(target_os = "android"))]
        {
            let len = u32::try_from(d.unsigned_abs()).ok()?.min(n);
            Some(in_steps(if d > 0 { 0 } else { n - len }, if d > 0 { len } else { n }, n))
        }
    };"""

SPAN_HELPER = """// VC_ANDROID15_ADAPTIVE_PAN: screen-only redraw granularity, not a lower
// image resolution. The finer 16-step spans always contain all newly exposed
// pixels. Use the original eighths when the drag exposes a larger fraction:
// they reuse existing renderer contexts and retain the earlier fallback rules.
#[cfg(any(target_os = "android", test))]
fn android15_pan_span(d: i64, n: u32) -> (u32, u32) {
    let len = u32::try_from(d.unsigned_abs()).unwrap_or(u32::MAX).min(n);
    let (a, b) = if d > 0 { (0, len) } else { (n - len, n) };
    if len <= n.div_ceil(8).max(1) {
        let step = n.div_ceil(16).max(1);
        let length = (b - a).max(1).div_ceil(step).saturating_mul(step).min(n);
        let start = a.min(n - length);
        (start, start + length)
    } else {
        in_steps(a, b, n)
    }
}

#[cfg(test)]
mod android15_pan_span_tests {
    use super::{android15_pan_span, in_steps};

    #[test]
    fn android15_pan_spans_never_leave_new_pixels_blank_or_extend_past_frame() {
        for n in [1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64,
                  65, 127, 128, 129, 257, 512, 720, 1080, 1440, 2048, 8192] {
            for shift in 1..=n.min(130) {
                for d in [i64::from(shift), -i64::from(shift)] {
                    let (a, b) = android15_pan_span(d, n);
                    let (exposed_a, exposed_b) =
                        if d > 0 { (0, shift) } else { (n - shift, n) };
                    assert!(a <= exposed_a && b >= exposed_b && b <= n && a <= b,
                            "n={n}, d={d}: [{a},{b}) must contain [{exposed_a},{exposed_b})");
                    let old = in_steps(exposed_a, exposed_b, n);
                    if shift <= n.div_ceil(8).max(1) {
                        assert!(b - a <= old.1 - old.0 + n.div_ceil(16).max(1),
                                "small pan must not materially expand render area");
                    } else {
                        assert_eq!((a, b), old, "large pan must keep original path");
                    }
                }
            }
        }
    }

    #[test]
    fn android15_small_swipes_reduce_typical_exposed_strip_pixels() {
        for n in [720, 1080, 1440, 2048, 4096] {
            let (a, b) = android15_pan_span(1, n);
            let (x, y) = in_steps(0, 1, n);
            assert!(b - a < y - x, "n={n}: finer strip must be narrower");
            assert_eq!(a, 0);
            assert_eq!(android15_pan_span(-1, n).1, n);
        }
    }
}

"""

ANCHOR_HELPER = """/// The parts \`[x0, y0, x1, y1]\` of a \`w\`×\`h\` frame that a pan by \`(dx, dy)\` device pixels exposes,"""

# Android.14's render_job body is left unchanged except a low-rate timing
# probe. Keep frame statistics opaque: no source document names, coordinates,
# text contents, image paths or linked resources are ever logged.
PROFILE_START_OLD = """pub(crate) fn render_job(r: &mut vectorcraft_render::Renderer, kept: &mut Option<KeptFrame>, job: &crate::render_worker::Job) -> WorkerFrame {
    let holds_pixels = kept.as_ref().is_none_or(|k| only_position_differs(k, job));"""
PROFILE_START_NEW = """pub(crate) fn render_job(r: &mut vectorcraft_render::Renderer, kept: &mut Option<KeptFrame>, job: &crate::render_worker::Job) -> WorkerFrame {
    // VC_ANDROID15_ADAPTIVE_PAN: sample low-rate worker render cost.
    #[cfg(target_os = "android")]
    let android15_job_started = std::time::Instant::now();
    let holds_pixels = kept.as_ref().is_none_or(|k| only_position_differs(k, job));"""

PROFILE_END_OLD = """    WorkerFrame { img, moved, reused }
}"""
PROFILE_END_NEW = """    // VC_ANDROID15_ADAPTIVE_PAN: avoid per-frame log spam. A sampled slow
    // job reports only duration, reused/full mode and pixel count, never art.
    #[cfg(target_os = "android")]
    {
        static SLOW_FRAME_SAMPLE: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
        let elapsed = android15_job_started.elapsed();
        if elapsed >= std::time::Duration::from_millis(24)
            && (SLOW_FRAME_SAMPLE.fetch_add(1, std::sync::atomic::Ordering::Relaxed) & 31) == 0
        {
            log::warn!(
                "VC_ANDROID15_RENDER_JOB duration_ms={} mode={} pixels={}",
                elapsed.as_millis(),
                if reused { "reused" } else { "full" },
                u64::from(job.w) * u64::from(job.h)
            );
        }
    }
    WorkerFrame { img, moved, reused }
}"""


def patch(root: Path) -> None:
    path = root / "source/vectorcraft/crates/ui-egui/src/canvas/raster.rs"
    source = path.read_text()
    # Source preflight is all-or-nothing. Android.13 and .14 must already be staged.
    expected = (
        (ORIGINAL_SPAN, 1),
        (ANCHOR_HELPER, 1),
        (PROFILE_START_OLD, 1),
        (PROFILE_END_OLD, 1),
        ("VC_ANDROID14_INPLACE_PAN", 3),  # multiple occurrences accepted below
    )
    for needle, expected_count in expected:
        count = source.count(needle)
        if (count != expected_count if needle != "VC_ANDROID14_INPLACE_PAN" else count < expected_count):
            raise ValueError(f"STOP: unexpected source anchor for {needle[:48]!r}: {count}")
    if MARKER in source:
        raise ValueError("STOP: Android.15 patch already applied")
    updated = source.replace(ANCHOR_HELPER, SPAN_HELPER + ANCHOR_HELPER, 1)
    updated = updated.replace(ORIGINAL_SPAN, SPAN_REPLACEMENT, 1)
    updated = updated.replace(PROFILE_START_OLD, PROFILE_START_NEW, 1)
    updated = updated.replace(PROFILE_END_OLD, PROFILE_END_NEW, 1)
    if updated.count(MARKER) < 3:
        raise ValueError("STOP: Android.15 adaptive strip patch incomplete")
    path.write_text(updated)
    print("PASS: Android.15 only small-pan redraw regions + low-rate worker diagnostics; still-frame and export untouched")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("builder", type=Path)
    patch(p.parse_args().builder)
