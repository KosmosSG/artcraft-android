#!/usr/bin/env python3
"""Extract only the approved FilmCraft launcher Fc glyph for a round wheel hub.

No new image design, font substitution, background tile or third-party assets.
Output is an 128 x 80 transparent RGBA raster loaded by egui on Android.
"""
from collections import Counter
from pathlib import Path
from PIL import Image


def render_logo(icon: Path, destination: Path):
    original = Image.open(icon).convert("RGBA")
    w, h = original.size
    if min(w, h) < 256:
        raise RuntimeError("STOP: approved Fc icon resolution too small")
    pixels = original.load()
    bg = pixels[w // 2, h // 8]
    if bg[3] < 235:
        raise RuntimeError("STOP: cannot establish approved launcher navy background")

    # Sample only central letterforms. Navbar/corner rounding is not part of
    # the glyph. Separate lavender ink by its strong red/green contrast against
    # the navy launcher tile, regardless of the asset's original dimensions.
    sampled = []
    stride = max(1, min(w, h) // 256)
    for y in range(h // 5, 4 * h // 5, stride):
        for x in range(w // 10, 9 * w // 10, stride):
            r, g, b, a = pixels[x, y]
            if a > 180 and r > bg[0] + 55 and g > bg[1] + 55:
                sampled.append((r, g, b))
    if len(sampled) < 100:
        raise RuntimeError("STOP: approved Fc lavender lettering not located")
    ink = Counter(sampled).most_common(1)[0][0]
    if ink[0] < bg[0] + 55 or ink[1] < bg[1] + 55:
        raise RuntimeError("STOP: Fc foreground/background separation ambiguous")

    mask = Image.new("L", original.size)
    alpha = mask.load()
    for y in range(h // 5, 4 * h // 5):
        for x in range(w // 10, 9 * w // 10):
            r, g, b, a = pixels[x, y]
            coverage = (r - bg[0]) / max(1, ink[0] - bg[0])
            alpha[x, y] = round(max(0, min(1, coverage)) * a) if a > 50 else 0
    bounds = mask.point(lambda a: 255 if a > 15 else 0).getbbox()
    if bounds is None:
        raise RuntimeError("STOP: Fc glyph extraction empty")
    x0, y0, x1, y1 = bounds
    if x0 < w * 0.05 or x1 > w * 0.95 or y0 < h * 0.12 or y1 > h * 0.88:
        raise RuntimeError(f"STOP: crop likely includes launcher square: {bounds}")
    if x1 - x0 < w * 0.38 or y1 - y0 < h * 0.24:
        raise RuntimeError(f"STOP: cropped Fc glyph unexpectedly small: {bounds}")

    glyph = Image.new("RGBA", original.size, (*ink, 0))
    glyph.putalpha(mask)
    glyph = glyph.crop(bounds)
    glyph.thumbnail((118, 67), Image.Resampling.LANCZOS)
    output = Image.new("RGBA", (128, 80), (0, 0, 0, 0))
    output.alpha_composite(glyph, ((128 - glyph.width) // 2, (80 - glyph.height) // 2))
    if output.getchannel("A").getbbox() is None:
        raise RuntimeError("STOP: Fc wheel glyph unexpectedly transparent")
    for point in [(0, 0), (127, 0), (0, 79), (127, 79), (0, 40), (127, 40)]:
        if output.getchannel("A").getpixel(point) > 8:
            raise RuntimeError("STOP: wheel logo includes rectangular tile edge")
    destination.write_bytes(output.tobytes())
    if destination.stat().st_size != 128 * 80 * 4:
        raise RuntimeError("STOP: wrong Fc glyph raster length")
    return bg[:3], ink


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("Usage: render_approved_fc_mark.py approved-Fc.png output.rgba")
    print(render_logo(Path(sys.argv[1]), Path(sys.argv[2])))
