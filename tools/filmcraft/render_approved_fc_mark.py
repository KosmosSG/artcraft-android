#!/usr/bin/env python3
"""Recreate only the Fc lettering from the user's original FilmCraft PNG.

A verified compact alpha mask of the user's navy/lavender icon is committed as
UTF-8 data. No guessed fonts, replacement app icons or external dependencies.
Output is egui's 128x80 transparent RGBA texture, not a square launcher tile.
"""
from pathlib import Path
from PIL import Image
import hashlib
import base64
import zlib

# Original user-supplied FilmCraft(1).png: navy (0,0,112), lavender (154,154,219).
NAVY = (0, 0, 112)
LAVENDER = (154, 154, 219)
ORIGINAL_MASK_SHA256 = "58cc9c327b867b774828bcf70d33c27a68f2a47ecfd706854d486620bf07b660"


def render_logo(mask_source: Path, destination: Path):
    encoded = mask_source.read_text().strip()
    compressed = base64.b64decode(encoded, validate=True)
    mask = zlib.decompress(compressed)
    if len(mask) != 96 * 60 or hashlib.sha256(mask).hexdigest() != ORIGINAL_MASK_SHA256:
        raise RuntimeError("STOP: original approved Fc glyph mask did not verify")
    alpha = Image.frombytes("L", (96, 60), mask).resize((128, 80), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (128, 80), (*LAVENDER, 0))
    out.putalpha(alpha)
    for point in [(0, 0), (127, 0), (0, 79), (127, 79), (0, 40), (127, 40)]:
        if out.getchannel("A").getpixel(point) > 8:
            raise RuntimeError("STOP: cropped Fc glyph has unexpected launcher tile edge")
    destination.write_bytes(out.tobytes())
    if destination.stat().st_size != 128 * 80 * 4:
        raise RuntimeError("STOP: wrong original Fc glyph raster size")
    return NAVY, LAVENDER


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("Usage: render_approved_fc_mark.py original-Fc-mask.b64 output.rgba")
    print(render_logo(Path(sys.argv[1]), Path(sys.argv[2])))
