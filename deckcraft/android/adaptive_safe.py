"""DeckCraft-only adaptive layer: extend red edges, retain one launcher mask."""
from pathlib import Path
import argparse
NEEDLE = '    stripped, _changed = _strip_background(work, pristine=pristine)\n    foreground = _foreground(Image, stripped)'
def patch(builder, app):
    if app != 'deckcraft': raise ValueError('DeckCraft only')
    p = Path(builder) / 'lib/app_icons.py'
    s = p.read_text()
    assert s.count(NEEDLE) == 1
    replacement = '''    if app == "deckcraft" and explicit is not None:
        size = round(CANVAS_PX * 0.66)
        tile = pristine.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        offset = (CANVAS_PX - size) // 2
        foreground = Image.new("RGBA", (CANVAS_PX, CANVAS_PX))
        for y in range(CANVAS_PX):
            for x in range(CANVAS_PX):
                foreground.putpixel((x, y), tile.getpixel((
                    max(0, min(size - 1, x - offset)),
                    max(0, min(size - 1, y - offset)))))
    else:
        stripped, _changed = _strip_background(work, pristine=pristine)
        foreground = _foreground(Image, stripped)'''
    p.write_text(s.replace(NEEDLE, replacement))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('builder'); parser.add_argument('app', choices=['deckcraft'])
    args = parser.parse_args(); patch(args.builder, args.app)
