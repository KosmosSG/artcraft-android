#!/usr/bin/env python3
"""CADCraft-only adaptive icon fix for a pinned Android reference checkout.

Use exact user-provided #D13153 and #F3E4E7 rather than sampling transparent
corners or exposing a monochrome icon for MagicOS to recolor.
This modifies only reference/lib/app_icons.py in the temporary Actions checkout.
"""
from pathlib import Path


def patch_reference(reference: Path) -> None:
    target = reference / "lib" / "app_icons.py"
    source = target.read_text(encoding="utf-8")
    anchor = "def generate(src: Path, app: str, res_dir: Path, explicit: Path = None) -> Path:"
    dispatch = "    source = pick_source(src, app, explicit)\n    work = _raster(source)"
    if source.count(anchor) != 1 or source.count(dispatch) != 1:
        raise SystemExit("Pinned reference icon builder changed; refusing unsafe CADCraft icon patch.")
    helper = '''
def _cadcraft_exact_icon(src: Path, app: str, res_dir: Path, explicit: Path) -> Path:
    """A branded adaptive icon with ample padding inside the MagicOS mask."""
    Image, _ = _pillow()
    original = Image.open(explicit).convert("RGBA")
    original.load()
    # Verify the source is the user's exact reference instead of tinting the
    # wrong upstream source (fail closed if the supplied asset changes).
    brand = (209, 49, 83)
    cream = (243, 228, 231)
    sx, sy = original.size
    sample = original.getpixel((sx // 2, sy // 6))
    if sample[:3] != brand or sample[3] < 250:
        raise SystemExit(f"CADCraft icon brand color mismatch: {sample}")
    (res_dir / "drawable").mkdir(parents=True, exist_ok=True)
    (res_dir / "drawable" / "ic_launcher_background.xml").write_text(
        _BG_XML.format(color="#D13153"), encoding="utf-8"
    )
    # Extract the cream 'Cc' without the rounded-square background and place
    # it well inside the adaptive safe zone. No second outer rounded square.
    work = original.resize((WORK_PX, WORK_PX), Image.Resampling.LANCZOS)
    glyph = Image.new("RGBA", work.size, (0, 0, 0, 0))
    src_pixels, out_pixels = work.load(), glyph.load()
    for y in range(105, 405):
        for x in range(58, 454):
            r, g, b, a = src_pixels[x, y]
            # Relative to the exact red background, cream has a much higher G
            # value. Preserve anti-aliased edge opacity with alpha coverage.
            coverage = max(0, min(255, round((g - 49) * 255 / (228 - 49))))
            if coverage > 1 and a > 0:
                out_pixels[x, y] = (*cream, round(a * coverage / 255))
    bbox = glyph.getbbox()
    if not bbox:
        raise SystemExit("Could not extract cream Cc glyph from source")
    glyph = glyph.crop(bbox)
    size = (round(ARTWORK_PX * 0.78 * glyph.width / max(glyph.width, glyph.height)),
            round(ARTWORK_PX * 0.78 * glyph.height / max(glyph.width, glyph.height)))
    glyph = glyph.resize(size, Image.Resampling.LANCZOS)
    # Legacy launchers also require real internal padding; do not put a second
    # rounded-square tile under the system adaptive mask.
    legacy = Image.new("RGBA", (WORK_PX, WORK_PX), (*brand, 255))
    legacy_glyph = glyph.resize((round(glyph.width * 0.94), round(glyph.height * 0.94)), Image.Resampling.LANCZOS)
    legacy.alpha_composite(legacy_glyph, ((WORK_PX - legacy_glyph.width) // 2, (WORK_PX - legacy_glyph.height) // 2))
    _write_legacy(explicit, legacy, res_dir)
    canvas = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), (0, 0, 0, 0))
    canvas.alpha_composite(glyph, ((CANVAS_PX - size[0]) // 2, (CANVAS_PX - size[1]) // 2))
    (res_dir / "drawable-xxxhdpi").mkdir(parents=True, exist_ok=True)
    canvas.save(res_dir / "drawable-xxxhdpi" / "ic_launcher_foreground.png")
    anydpi = res_dir / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    # Disable forced Android themed-icon monochrome tint ONLY for CADCraft.
    adaptive = _ADAPTIVE_XML.replace(
        '    <monochrome android:drawable="@drawable/ic_launcher_foreground" />\\n',
        "",
    )
    (anydpi / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")
    return explicit


'''
    replacement = "    if app == 'cadcraft' and explicit is not None:\n        return _cadcraft_exact_icon(src, app, res_dir, explicit)\n" + dispatch
    source = source.replace(anchor, helper + anchor, 1)
    source = source.replace(dispatch, replacement, 1)
    target.write_text(source, encoding="utf-8")
    print("PASS: CADCraft-only exact brand adaptive icon; no MagicOS monochrome tint.")
