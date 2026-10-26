"""Package the owner's Ec tile with a transparent exterior and safe adaptive inset."""
from collections import deque
from pathlib import Path
import hashlib
from PIL import Image

SOURCE_SHA = "548b40f2997037c5861c602fecfad71ef8bf3c78ad9e6189c8409d0a78629b0b"

def generate(source, destination):
    source, destination = Path(source), Path(destination)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError("Unexpected Ec artwork")
    tile = Image.open(source).convert("RGBA")
    w, h = tile.size
    pixels = tile.load()
    seen = set()
    queue = deque([(x, 0) for x in range(w)] + [(x, h-1) for x in range(w)] +
                  [(0, y) for y in range(h)] + [(w-1, y) for y in range(h)])
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen: continue
        seen.add((x, y))
        r, g, b, a = pixels[x, y]
        if a and max(r, g, b) > 32: continue
        pixels[x, y] = (r, g, b, 0)
        queue.extend((nx, ny) for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1))
                     if 0 <= nx < w and 0 <= ny < h)
    bounds = tile.getchannel("A").getbbox()
    if not bounds: raise ValueError("Empty icon")
    tile = tile.crop(bounds)
    for density, size in {"mdpi":48,"hdpi":72,"xhdpi":96,"xxhdpi":144,"xxxhdpi":192}.items():
        folder = destination / ("mipmap-" + density)
        folder.mkdir(parents=True, exist_ok=True)
        tile.resize((size,size), Image.Resampling.LANCZOS).save(folder / "ic_launcher.png")
    foreground = Image.new("RGBA", (432,432))
    # Entire tile is inside the adaptive icon safe region; glass letters cannot clip.
    foreground.alpha_composite(tile.resize((256,256), Image.Resampling.LANCZOS), (88,88))
    folder = destination / "drawable-xxxhdpi"
    folder.mkdir(parents=True, exist_ok=True)
    foreground.save(folder / "ic_launcher_foreground.png")
    color = tile.getpixel((tile.width // 2, max(1, tile.height // 20)))[:3]
    folder = destination / "values"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ec_icon_colors.xml").write_text('<resources><color name="ec_icon_bg">#%02x%02x%02x</color></resources>' % color)
    folder = destination / "mipmap-anydpi-v26"
    folder.mkdir(parents=True, exist_ok=True)
    xml = '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/ec_icon_bg"/><foreground android:drawable="@drawable/ic_launcher_foreground"/></adaptive-icon>'
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (folder / name).write_text(xml)
