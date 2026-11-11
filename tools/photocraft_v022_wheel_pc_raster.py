#!/usr/bin/env python3
"""Render the user-provided, unchanged vector Pc mark for the PhotoCraft wheel.

Outputs 192x120 raw RGBA bytes. The vector path, color, and transparent
background come directly from the supplied Adobe Illustrator SVG.
"""
import argparse
import io
from pathlib import Path
import cairosvg
from PIL import Image

WIDTH, HEIGHT = 192, 120

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    opt = parser.parse_args()
    source = opt.svg.read_bytes()
    if b'<svg' not in source or b'#27a5de' not in source:
        raise SystemExit("Refusing an unexpected or recolored Pc icon")
    png = cairosvg.svg2png(bytestring=source, output_width=512, output_height=512)
    picture = Image.open(io.BytesIO(png)).convert("RGBA")
    bbox = picture.getchannel("A").getbbox()
    if not bbox:
        raise SystemExit("The supplied Pc logo has no visible pixels")
    logo = picture.crop(bbox)
    logo.thumbnail((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    canvas.alpha_composite(logo, ((WIDTH - logo.width)//2, (HEIGHT-logo.height)//2))
    result = canvas.tobytes()
    if len(result) != WIDTH * HEIGHT * 4:
        raise SystemExit("Unexpected wheel image byte size")
    opt.output.parent.mkdir(parents=True, exist_ok=True)
    opt.output.write_bytes(result)
    print(f"Pc user SVG: {logo.width}x{logo.height} in {WIDTH}x{HEIGHT} transparent RGBA, {len(result)} bytes")
if __name__ == "__main__":
    main()
