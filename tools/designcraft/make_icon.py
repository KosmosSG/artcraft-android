"""Package the approved DesignCraft glossy Dc artwork for Android.

approved-dc.webp is an optimized, safe-area composite of the user-approved
magenta Dc icon. Its original glossy glyphs are retained; the black exterior
is replaced by an opaque burgundy background. Do not redraw, auto-trim,
stretch the lettering separately, or pre-mask the icon corners.
"""
from pathlib import Path
from PIL import Image
import hashlib
import sys

ARTWORK = Path(__file__).with_name("approved-dc.webp")
ARTWORK_SHA256 = "2ce2ea8e165fd52dcb56cced65e1a9af1181987cbf3bfeadd052e07189abc19e"
EXPECTED_SIZE = (512, 512)


def draw_icon(path):
    source_bytes = ARTWORK.read_bytes()
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != ARTWORK_SHA256:
        raise ValueError("DesignCraft approved icon asset checksum mismatch")
    with Image.open(ARTWORK) as approved:
        if approved.size != EXPECTED_SIZE:
            raise ValueError("Unexpected DesignCraft icon dimensions")
        # This composited artwork already respects Android's adaptive safe area.
        # Scale the whole tile together, never the glyphs alone.
        image = approved.convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "PNG")
    return out


if __name__ == "__main__":
    draw_icon(sys.argv[1])
