#!/usr/bin/env python3
"""FilmCraft-only PhotoCraft-quality white wheel icons, fixed open-source SVG art.

Lucide icons v0.456.0 (ISC license), pinned to upstream tag
f93beca5957187620e30ae771d220d88501be621.
Icons: scissors (Razor), mouse-pointer-2, hand, undo-2, redo-2,
zoom-in, zoom-out. Play/pause is a simple original combination.
The CI-only SVG renderer creates 8 RGBA tiles at 72x72 px. No network or
new Android runtime dependency is required.
"""
import io
from pathlib import Path
import sys
import tempfile

import cairosvg
from PIL import Image

TILE = 72
NAMES = ("scissors", "pointer", "hand", "undo", "redo",
         "playpause", "zoomin", "zoomout")
SVG = {"scissors":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <circle cx=\"6\" cy=\"6\" r=\"3\" />\n  <path d=\"M8.12 8.12 12 12\" />\n  <path d=\"M20 4 8.12 15.88\" />\n  <circle cx=\"6\" cy=\"18\" r=\"3\" />\n  <path d=\"M14.8 14.8 20 20\" />\n</svg>\n","pointer":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <path d=\"M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z\" />\n</svg>\n","hand":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <path d=\"M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2\" />\n  <path d=\"M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2\" />\n  <path d=\"M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8\" />\n  <path d=\"M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15\" />\n</svg>\n","undo":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <path d=\"M9 14 4 9l5-5\" />\n  <path d=\"M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11\" />\n</svg>\n","redo":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <path d=\"m15 14 5-5-5-5\" />\n  <path d=\"M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13\" />\n</svg>\n","playpause":"<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" width=\"24\" height=\"24\" fill=\"none\" stroke=\"white\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"m3 4 10 8-10 8z\" fill=\"white\" stroke=\"none\"/><rect x=\"16\" y=\"4\" width=\"2\" height=\"16\" rx=\"1\" fill=\"white\" stroke=\"none\"/><rect x=\"21\" y=\"4\" width=\"2\" height=\"16\" rx=\"1\" fill=\"white\" stroke=\"none\"/></svg>","zoomin":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <circle cx=\"11\" cy=\"11\" r=\"8\" />\n  <line x1=\"21\" x2=\"16.65\" y1=\"21\" y2=\"16.65\" />\n  <line x1=\"11\" x2=\"11\" y1=\"8\" y2=\"14\" />\n  <line x1=\"8\" x2=\"14\" y1=\"11\" y2=\"11\" />\n</svg>\n","zoomout":"<svg\n  xmlns=\"http://www.w3.org/2000/svg\"\n  width=\"24\"\n  height=\"24\"\n  viewBox=\"0 0 24 24\"\n  fill=\"none\"\n  stroke=\"currentColor\"\n  stroke-width=\"2\"\n  stroke-linecap=\"round\"\n  stroke-linejoin=\"round\"\n>\n  <circle cx=\"11\" cy=\"11\" r=\"8\" />\n  <line x1=\"21\" x2=\"16.65\" y1=\"21\" y2=\"16.65\" />\n  <line x1=\"8\" x2=\"14\" y1=\"11\" y2=\"11\" />\n</svg>\n"}

def render_icons(destination: Path) -> None:
    sheet = Image.new("RGBA", (TILE, TILE * len(NAMES)), (0, 0, 0, 0))
    for i, name in enumerate(NAMES):
        src = SVG[name].replace("currentColor", "#ffffff")
        png = cairosvg.svg2png(bytestring=src.encode("utf-8"),
                              output_width=TILE, output_height=TILE)
        tile = Image.open(io.BytesIO(png)).convert("RGBA")
        if tile.getbbox() is None or tile.getchannel("A").getextrema()[1] < 240:
            raise RuntimeError(f"STOP: missing/bad icon raster: {name}")
        sheet.alpha_composite(tile, (0, i * TILE))
    destination.write_bytes(sheet.tobytes())
    if destination.stat().st_size != TILE * TILE * len(NAMES) * 4:
        raise RuntimeError("STOP: wrong FilmCraft sprite dimensions")

def main():
    if sys.argv[1:] == ["--self-test"]:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "icons.rgba"
            render_icons(target)
            print("PASS: eight quality 72px white anti-aliased wheel icons: ",
                  target.stat().st_size, "RGBA bytes")
    elif len(sys.argv) == 2:
        render_icons(Path(sys.argv[1]))
    else:
        raise SystemExit("Usage: render_filmcraft_wheel_icons.py [--self-test | path.rgba]")

if __name__ == "__main__":
    main()
