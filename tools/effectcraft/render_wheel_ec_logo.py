#!/usr/bin/env python3
"""Rasterize the actual approved Ec launcher glyph for the wheel (no font substitution).

Read the exact owner-approved 2048px EffectCraft art, isolate lavender glyphs
using the manifest's color and crop bounds, and generate embedded RGBA pixels.
This is a build-only conversion; no runtime decoder, permissions or font files.
"""
from pathlib import Path
import hashlib
import json
import sys

from PIL import Image

WIDTH, HEIGHT = 192, 126

def render(root: Path) -> Path:
    root = root.resolve()
    directory = root / "tools/approved-branding/assets"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["app"] == "effectcraft"
    assert manifest["filename"] == "EffectCraft.png"
    image = directory / manifest["filename"]
    actual = hashlib.sha256(image.read_bytes()).hexdigest()
    assert actual == manifest["source_sha256"], "STOP: approved Ec logo artwork changed"
    assert manifest["bg_color"].lower() == "#060084"
    assert manifest["letter_color"].lower() == "#9999ff"
    assert manifest["glyph_source_bounds"] == [401, 597, 1728, 1468]
    original = Image.open(image).convert("RGBA")
    assert original.size == (2048, 2048), "STOP: unexpected icon dimensions"
    glyph = original.crop(tuple(manifest["glyph_source_bounds"]))
    bg_r = 6
    glyph_r = 153
    # The source's antialiased lettering is a blend of the verified brand
    # lavender and deep blue. Recover its per-pixel coverage; keep all the
    # distinctive straight E and open c contours in the exact proportions.
    alpha = glyph.getchannel("R").point(
        lambda value: round(max(0.0, min(1.0, (value - bg_r) / (glyph_r - bg_r))) * 255)
    )
    logo = Image.new("RGBA", glyph.size, (153, 153, 255, 0))
    logo.putalpha(alpha)
    logo = logo.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    if logo.getchannel("A").getbbox() is None:
        raise RuntimeError("STOP: extracted Ec lettering is empty")
    target = root / "source/effectcraft/crates/ui-egui/src/stylus_wheel_ec.rgba"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(logo.tobytes())
    assert target.stat().st_size == WIDTH * HEIGHT * 4
    print(f"PASS: approved Ec launcher lettering embedded as {WIDTH}x{HEIGHT} RGBA; SHA256 {actual}")
    return target

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_wheel_ec_logo.py <artcraft-repo-root>")
    render(Path(sys.argv[1]))
