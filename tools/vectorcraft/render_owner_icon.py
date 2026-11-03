"""Render the owner's 2026-11-03 orange Vc icon as an Android PNG.

The tiny lossless vector geometry is traced from the user's 2048px PNG.
Use Pillow only (no network, fonts or SVG rasterizer) so the approved image
does not silently fall back to the previous glossy Vc icon.
"""
from pathlib import Path
import argparse
import re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

BRAND_BG = "#2d0000"
BRAND_LETTERS = "#ff9f00"

def render(source: Path, dest: Path, side: int = 1024) -> None:
    if side < 512 or side > 2048:
        raise ValueError("Icon size must be 512–2048 pixels")
    root = ET.parse(source).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    bg = root.find(ns + "rect")
    path = root.find(ns + "path")
    if bg is None or path is None or bg.get("fill") != BRAND_BG or path.get("fill") != BRAND_LETTERS:
        raise ValueError("Owner's Vc SVG branding changed unexpectedly")
    if root.get("viewBox") != "0 0 512 512":
        raise ValueError("Owner artwork viewport changed")
    # Render at 2x and downsample for smooth antialiasing.
    scale = side * 2 / 512
    big = side * 2
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    paint = ImageDraw.Draw(img)
    paint.rounded_rectangle((0, 0, big - 1, big - 1),
                            radius=round(75 * scale), fill=BRAND_BG)
    tokens = re.findall(r"[MLZ]|\d+", path.get("d", ""))
    polygons = []
    i = 0
    polygon = []
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd in ("M", "L"):
            if i + 1 >= len(tokens):
                raise ValueError("Incomplete Vc letter vertex")
            x, y = int(tokens[i]), int(tokens[i + 1])
            i += 2
            if cmd == "M":
                if polygon:
                    raise ValueError("Unclosed owner letter contour")
                polygon = []
            polygon.append((round(x * scale), round(y * scale)))
        elif cmd == "Z":
            if len(polygon) < 3:
                raise ValueError("Invalid owner letter contour")
            polygons.append(polygon)
            polygon = []
        else:
            raise ValueError("Unsupported Vc SVG command")
    if len(polygons) != 2 or polygon:
        raise ValueError("Exactly two approved Vc letter contours expected")
    for polygon in polygons:
        paint.polygon(polygon, fill=BRAND_LETTERS)
    out = img.resize((side, side), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "PNG", optimize=True)
    assert out.getpixel((side//2, side//2))[:3] == (45, 0, 0) or out.getpixel((side//2, side//2))[0] > 100
    print(f"PASS: owner orange Vc logo {side}x{side} RGBA, transparent rounded outside corners")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("dest",type=Path)
    parser.add_argument("--size",type=int,default=1024)
    args=parser.parse_args()
    render(args.source,args.dest,args.size)
