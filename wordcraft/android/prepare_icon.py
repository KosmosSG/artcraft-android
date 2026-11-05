"""Remove baked black corners from the approved Wc launcher derivative.

Only border-connected dark pixels are replaced. Glass lettering and the
approved source WEBP remain unchanged. Android supplies the launcher mask.
"""
from collections import deque
from pathlib import Path
from PIL import Image
import sys

BRAND = (0, 53, 140, 255)


def normalize(source: Path, destination: Path):
    image = Image.open(source).convert("RGBA")
    w, h = image.size
    if (w, h) != (192, 192):
        raise ValueError("Review different source artwork before normalizing")
    pixels = image.load()
    queue = deque([(x, y) for x in range(w) for y in (0, h - 1)]
                  + [(x, y) for y in range(h) for x in (0, w - 1)])
    seen = set()
    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        r, g, b, a = pixels[x, y]
        if a > 200 and b >= 120:
            continue
        pixels[x, y] = BRAND
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    image.save(destination)


if __name__ == "__main__":
    normalize(Path(sys.argv[1]), Path(sys.argv[2]))
