"""Render the approved glossy DesignCraft 'Dc' launcher artwork.

The source image is designcraft-specific and intentionally opaque. Never
redraw the letters with a font or pre-round the image corners: Android's
adaptive launcher icon supplies the rounded-square mask.
"""
from pathlib import Path
from PIL import Image
import hashlib
import sys

ARTWORK = Path(__file__).with_name("approved-dc.webp")
ARTWORK_SHA256 = "3906b7071dc8827f4648cd842fc586704ef584d46939a59731da1d2da013fa5e"


def draw_icon(path):
    original = ARTWORK.read_bytes()
    if hashlib.sha256(original).hexdigest() != ARTWORK_SHA256:
        raise ValueError("Approved DesignCraft icon asset was modified or corrupted")
    with Image.open(ARTWORK) as source:
        if source.size != (256, 256):
            raise ValueError("Unexpected approved DesignCraft icon dimensions")
        image = source.convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return output


if __name__ == "__main__":
    draw_icon(sys.argv[1])
