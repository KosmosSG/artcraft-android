"""Render the approved glossy DesignCraft Dc icon within Android's adaptive safe area.

The approved artwork is kept pixel-for-pixel: no font redraw or flattened letters.
Adaptive launcher masks only guarantee visibility inside the middle 72dp of the
108dp canvas. Previously stretching the whole tile to 108dp cropped the D and c
on HONOR launchers; this creates a branded, full-bleed background and positions
the original glossy lettering inside that guaranteed visible area.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import hashlib
import sys

ARTWORK = Path(__file__).with_name("approved-dc.webp")
ARTWORK_SHA256 = "3906b7071dc8827f4648cd842fc586704ef584d46939a59731da1d2da013fa5e"
SIZE = 1024
# Only surrounding background is trimmed; the glass Dc itself remains intact.
LETTER_CROP = (105, 190, 942, 835)
SAFE_ART_WIDTH = 630
EDGE_FEATHER = 22


def draw_icon(path):
    original = ARTWORK.read_bytes()
    if hashlib.sha256(original).hexdigest() != ARTWORK_SHA256:
        raise ValueError("Approved DesignCraft icon asset was modified or corrupted")
    with Image.open(ARTWORK) as source:
        if source.size != (256, 256):
            raise ValueError("Unexpected approved DesignCraft icon dimensions")
        approved = source.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)

    # Reconstruct only the subtle burgundy background from the clear, letter-free
    # source edges. Keep it opaque all the way to the Android launcher mask.
    image = Image.new("RGB", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        left = approved.getpixel((24, y))
        right = approved.getpixel((999, y))
        color = tuple((left[channel] + right[channel]) // 2 for channel in range(3))
        draw.line((0, y, SIZE - 1, y), fill=color)

    art = approved.crop(LETTER_CROP)
    width = SAFE_ART_WIDTH
    height = round(art.height * width / art.width)
    art = art.resize((width, height), Image.Resampling.LANCZOS)

    # Blend the cropped tile's background into the full-bleed gradient without
    # affecting the glossy lettering, which is safely away from these edges.
    mask = Image.new("L", (width, height), 0)
    pixels = mask.load()
    for y in range(height):
        for x in range(width):
            edge = min(x, width - 1 - x, y, height - 1 - y)
            t = min(1.0, edge / EDGE_FEATHER)
            pixels[x, y] = round(255 * t * t * (3 - 2 * t))

    image.paste(art, ((SIZE - width) // 2, (SIZE - height) // 2), mask)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG")
    return output


if __name__ == "__main__":
    draw_icon(sys.argv[1])
