"""Package the approved Dc tile without its surrounding black presentation canvas."""
from collections import deque
import hashlib
from pathlib import Path
from PIL import Image

APPROVED_SHA256 = "306fb5fd3efdb138eee5d0b7c0c34b91718229c60408e92af4bba949daecea9d"
STAGED_PNG_SHA256 = "df27b2f46cfad9df7493ee88da9265fc7de2d62313361746d9bc0ecd5dd6803b"
CANVAS = 432
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def tile_from_source(source):
    source = Path(source)
    if hashlib.sha256(source.read_bytes()).hexdigest() not in (APPROVED_SHA256, STAGED_PNG_SHA256):
        raise ValueError("Launcher artwork differs from the approved Dc source")
    with Image.open(source) as opened:
        tile = opened.convert("RGBA")
    # Only near-black pixels connected to the exterior are cleared. Interior
    # shadows and every part of the original glass lettering remain intact.
    w, h = tile.size
    pixels = tile.load()
    seen = bytearray(w * h)
    queue = deque([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
                  + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    while queue:
        x, y = queue.popleft()
        index = y * w + x
        if seen[index]:
            continue
        seen[index] = 1
        r, g, b, a = pixels[x, y]
        if a > 0 and max(r, g, b) > 32:
            continue
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                queue.append((nx, ny))
    # Remove a few near-black interior compression specks as well. Even four
    # opaque black pixels can show as a dark halo on MagicOS adaptive masks.
    # The original magenta glass lettering and burgundy tile remain intact.
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a and max(r, g, b) <= 40:
                pixels[x, y] = (r, g, b, 0)
    bounds = tile.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Approved launcher tile is empty")
    tile = tile.crop(bounds)
    # Take the actual burgundy background from the tile, not its removed canvas.
    color = tile.getpixel((tile.width // 2, max(1, tile.height // 20)))[:3]
    return tile, color


def generate(source, destination):
    destination = Path(destination)
    tile, color = tile_from_source(source)
    for density, size in DENSITIES.items():
        folder = destination / ("mipmap-" + density)
        folder.mkdir(parents=True, exist_ok=True)
        tile.resize((size, size), Image.Resampling.LANCZOS).save(folder / "ic_launcher.png")
    # Fit the artwork within Android's safe region inside the 72dp viewport.
    # This preserves the glass lettering even with a circular mask. The background
    # extends under every launcher mask; no black frame is baked into either layer.
    tile_size = round(CANVAS * 64 / 108)
    foreground = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    fitted = tile.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    # Lanczos can reintroduce a handful of near-black samples after cleanup.
    # Clear only residual dark specks in the adaptive foreground; the solid
    # burgundy layer beneath fills their places without a black outline.
    filtered = fitted.load()
    for fy in range(fitted.height):
        for fx in range(fitted.width):
            r, g, b, a = filtered[fx, fy]
            if a and max(r, g, b) < 52:
                filtered[fx, fy] = (r, g, b, 0)
    foreground.alpha_composite(fitted, ((CANVAS-tile_size)//2, (CANVAS-tile_size)//2))
    folder = destination / "drawable-xxxhdpi"
    folder.mkdir(parents=True, exist_ok=True)
    foreground.save(folder / "ic_launcher_foreground.png")
    folder = destination / "drawable"
    folder.mkdir(parents=True, exist_ok=True)
    hexcolor = "#%02X%02X%02X" % color
    (folder / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">'
        f'<solid android:color="{hexcolor}" /></shape>\n')
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
           '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">'
           '<background android:drawable="@drawable/ic_launcher_background" />'
           '<foreground android:drawable="@drawable/ic_launcher_foreground" />'
           '</adaptive-icon>\n')
    folder = destination / "mipmap-anydpi-v26"
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (folder / name).write_text(xml)
    return Path(source)
