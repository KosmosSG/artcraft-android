"""Android.14: reuse the existing worker pixel buffer for cached whole-pixel panning.

Pinned upstream VectorCraft v0.24.1 already has view reprojection, image mips,
low-res fill, partial rendering, and shared image caching. Do not duplicate or
weaken them. The old worker pan allocated a zero-filled RGBA frame, then copied
every preserved row into it before rendering exposed strips. On Android, move
those rows inside the owned old RGBA allocation instead. Export, geometry,
painting, texture dimensions, full-resolution still frames, and CPU rasterizer
remain unchanged. A host-only Rust test compares every byte with the previous
algorithm for many positive/negative pan offsets.

Patches only the disposable builder checkout, rejects unreviewed anchors, and
does not alter the published production branch or signing.
"""
from pathlib import Path
import argparse

MARKER = "VC_ANDROID14_INPLACE_PAN"

ANCHOR_FUNC = """/// The frame of """
ANCHOR_COPY = """    let copied = kept.as_ref().and_then(|k| {
        let pan = whole_pixel_pan(k, job)?;
        let parts = exposed_parts(job.w, job.h, pan)?;
        composed_frame(r, moved_pixels(k.pixels.as_ref()?, job.w, job.h, pan), parts, job)
    });"""

FAST = """// VC_ANDROID14_INPLACE_PAN: reuse the previous worker RGBA allocation.
// Positive vertical moves copy bottom-up; negative moves copy top-down,
// preventing overlapping source rows from being overwritten. Within a row
// copy_within handles left/right overlap. Zero only newly exposed strips.
// This path affects screen-space cached pan pixels, not the original image or
// saved/exported documents. The normal fallback still fully renders the art.
#[cfg(any(target_os = "android", test))]
fn moved_pixels_in_place(mut pixels: Vec<u8>, w: u32, h: u32, (dx, dy): (i64, i64)) -> Vec<u8> {
    let width = w as usize;
    let height = h as usize;
    let stride = width.saturating_mul(4);
    if width == 0 || height == 0 || pixels.len() != stride.saturating_mul(height) {
        return moved_pixels(&pixels, w, h, (dx, dy));
    }
    let abs_dx = dx.unsigned_abs() as usize;
    let abs_dy = dy.unsigned_abs() as usize;
    if abs_dx >= width || abs_dy >= height {
        pixels.fill(0);
        return pixels;
    }
    let span_w = width - abs_dx;
    let span_h = height - abs_dy;
    let src_x = if dx > 0 { 0 } else { abs_dx };
    let dest_x = if dx > 0 { abs_dx } else { 0 };
    let src_y = if dy > 0 { 0 } else { abs_dy };
    let dest_y = if dy > 0 { abs_dy } else { 0 };
    let copy_row = |row: usize, pixels: &mut Vec<u8>| {
        let from = (src_y + row) * stride + src_x * 4;
        let to = (dest_y + row) * stride + dest_x * 4;
        pixels.copy_within(from..from + span_w * 4, to);
    };
    if dy > 0 {
        for row in (0..span_h).rev() {
            copy_row(row, &mut pixels);
        }
    } else {
        for row in 0..span_h {
            copy_row(row, &mut pixels);
        }
    }
    if dy > 0 {
        pixels[..dest_y * stride].fill(0);
    } else if dy < 0 {
        pixels[(dest_y + span_h) * stride..].fill(0);
    }
    for row in dest_y..dest_y + span_h {
        let offset = row * stride;
        if dx > 0 {
            pixels[offset..offset + dest_x * 4].fill(0);
        } else if dx < 0 {
            pixels[offset + (dest_x + span_w) * 4..offset + stride].fill(0);
        }
    }
    pixels
}

#[cfg(test)]
mod android14_inplace_pan_tests {
    use super::{moved_pixels, moved_pixels_in_place};

    #[test]
    fn android14_inplace_pan_matches_original_pixels_in_every_direction() {
        for w in 1u32..=13 {
            for h in 1u32..=9 {
                let src: Vec<u8> = (0..w as usize * h as usize * 4)
                    .map(|i| ((i * 37 + 11) % 251) as u8).collect();
                for dy in -(i64::from(h) + 2)..=(i64::from(h) + 2) {
                    for dx in -(i64::from(w) + 2)..=(i64::from(w) + 2) {
                        let expected = moved_pixels(&src, w, h, (dx, dy));
                        let actual = moved_pixels_in_place(src.clone(), w, h, (dx, dy));
                        assert_eq!(actual, expected, "w={w} h={h} dx={dx} dy={dy}");
                    }
                }
            }
        }
    }
}

"""

AFTER_COPY = """    let copied = kept.as_mut().and_then(|k| {
        let pan = whole_pixel_pan(k, job)?;
        let parts = exposed_parts(job.w, job.h, pan)?;
        // VC_ANDROID14_INPLACE_PAN: consume the worker's old pixels instead of
        // allocating another full frame on Android. A failed partial render
        // follows the existing full-frame fallback and replaces kept anyway.
        #[cfg(target_os = "android")]
        let shifted = moved_pixels_in_place(k.pixels.take()?, job.w, job.h, pan);
        #[cfg(not(target_os = "android"))]
        let shifted = moved_pixels(k.pixels.as_ref()?, job.w, job.h, pan);
        composed_frame(r, shifted, parts, job)
    });"""


def patch(root: Path) -> None:
    file = root / "source/vectorcraft/crates/ui-egui/src/canvas/raster.rs"
    source = file.read_text()
    if MARKER in source or source.count(ANCHOR_FUNC) != 1 or source.count(ANCHOR_COPY) != 1:
        raise ValueError("STOP: pinned VectorCraft canvas raster anchors changed or patch applied")
    changed = source.replace(ANCHOR_FUNC, FAST + ANCHOR_FUNC, 1)
    changed = changed.replace(ANCHOR_COPY, AFTER_COPY, 1)
    if changed.count("VC_ANDROID14_INPLACE_PAN") < 2:
        raise ValueError("STOP: incomplete pan optimization")
    file.write_text(changed)
    print("PASS: Android.14 pixel-buffer reuse for native heavy .ai panning; desktop and export paths unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    patch(parser.parse_args().builder)
