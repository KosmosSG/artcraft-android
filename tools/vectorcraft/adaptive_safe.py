"""Scope approved suite launcher artwork to Android's adaptive safe area.

The uploaded source image and legacy launcher mipmaps remain unchanged.
Only the pinned disposable builder's adaptive foreground computation changes.
No source-app, signing or production release file is modified.
"""
import argparse
from pathlib import Path

NEEDLE = (
    "    stripped, _changed = _strip_background(work, pristine=pristine)\n"
    "    foreground = _foreground(Image, stripped)"
)
APPS = {"vectorcraft", "filmcraft", "wordcraft", "deckcraft"}

def patch(builder, app):
    if app not in APPS:
        raise ValueError("Unreviewed app; refusing builder modification")
    module = Path(builder) / "lib" / "app_icons.py"
    source = module.read_text()
    if source.count(NEEDLE) != 1:
        raise ValueError("Pinned builder adaptive icon code changed: review required")
    if app == "vectorcraft":
        # The owner now supplied the FLAT orange Vc on a deep-maroon tile.
        # Use only the glyphs in the adaptive foreground, because Android itself
        # masks the background to the device's launcher shape. Keeping the
        # rounded-square tile in the foreground causes the unwanted double mask.
        injected = '''    if app == "vectorcraft" and explicit is not None:
        from PIL import Image
        work_icon = pristine.convert("RGBA")
        mask = Image.new("L", work_icon.size)
        mask.putdata([alpha if red > 150 and green > 60 and red > green * 1.3
                      else 0 for red, green, blue, alpha in work_icon.getdata()])
        work_icon.putalpha(mask)
        tile_size = round(CANVAS_PX * 0.82)
        glyph = work_icon.resize((tile_size, tile_size), Image.LANCZOS)
        foreground = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), (0, 0, 0, 0))
        foreground.alpha_composite(glyph,
            ((CANVAS_PX - tile_size) // 2, (CANVAS_PX - tile_size) // 2))
    else:
        stripped, _changed = _strip_background(work, pristine=pristine)
        foreground = _foreground(Image, stripped)'''
    else:
        injected = '''    if app == "APP_ID" and explicit is not None:
        from PIL import ImageChops
        tile_size = round(CANVAS_PX * 0.61)
        tile = pristine.resize((tile_size, tile_size), Image.LANCZOS)
        feather = Image.new("L", (tile_size, tile_size), 0)
        px = feather.load()
        for yy in range(tile_size):
            for xx in range(tile_size):
                edge = min(xx, yy, tile_size - 1 - xx, tile_size - 1 - yy)
                t = min(1.0, edge / 16.0)
                px[xx, yy] = round(255 * t * t * (3 - 2 * t))
        tile.putalpha(ImageChops.multiply(tile.getchannel("A"), feather))
        foreground = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), color)
        foreground.alpha_composite(
            tile, ((CANVAS_PX - tile_size) // 2, (CANVAS_PX - tile_size) // 2)
        )
    else:
        stripped, _changed = _strip_background(work, pristine=pristine)
        foreground = _foreground(Image, stripped)'''.replace("APP_ID", app)
    module.write_text(source.replace(NEEDLE, injected))
    print(f"PASS: approved {app} artwork padded for Android adaptive icon")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("app", choices=sorted(APPS))
    args = parser.parse_args()
    patch(args.builder, args.app)
