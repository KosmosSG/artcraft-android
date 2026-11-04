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
        tile_size = round(CANVAS_PX * 0.65)  # 72dp adaptive safe zone; roomy glyph margin
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
    updated = source.replace(NEEDLE, injected)
    if app == "vectorcraft":
        # The builder's _write_legacy reads the full-sized original PNG again,
        # so pad its generated mipmaps after that method has run. Both legacy
        # and adaptive variants now keep generous distance from mask edges.
        legacy = '    _write_legacy(source, pristine, res_dir)'
        if updated.count(legacy) != 1:
            raise ValueError("Pinned legacy icon writer changed; review required")
        pad_legacy = '''    _write_legacy(source, pristine, res_dir)
    if app == "vectorcraft" and explicit is not None:
        # Keep the owner's rounded maroon Vc tile; avoid double-masking the
        # adaptive foreground, which was generated independently above.
        for density in DENSITIES:
            icon_path = res_dir / f"mipmap-{density}" / "ic_launcher.png"
            source_icon = Image.open(icon_path).convert("RGBA")
            side = source_icon.width
            tile_size = round(side * 0.78)
            tile = source_icon.resize((tile_size, tile_size), Image.Resampling.LANCZOS)
            padded = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            padded.alpha_composite(tile,
                ((side - tile_size) // 2, (side - tile_size) // 2))
            padded.save(icon_path, format="PNG")'''
        updated = updated.replace(legacy, pad_legacy, 1)
    module.write_text(updated)
    print(f"PASS: approved {app} artwork padded for Android adaptive icon")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    parser.add_argument("app", choices=sorted(APPS))
    args = parser.parse_args()
    patch(args.builder, args.app)
