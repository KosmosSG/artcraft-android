
# GRIDCRAFT_USER_ADAPTIVE_ICON_V1
# Only the owner-supplied Gc icon overrides the builder's generic floodfill.
# Keep legacy mipmaps from that PNG, but strip the green tile from the adaptive
# foreground so Android applies its adaptive mask once (no double-rounding).
_original_app_icons_generate = generate

def generate(src, app, res_dir, explicit=None):
    chosen = _original_app_icons_generate(src, app, res_dir, explicit)
    if app != "gridcraft" or explicit is None:
        return chosen
    import hashlib
    from PIL import Image
    png = Path(explicit).read_bytes()
    expected = "e35af23c45ee75e1e026374c7b2458ac9f616cc82ffe39465f9c0ad3f3aeb7b2"
    if hashlib.sha256(png).hexdigest() != expected:
        raise RuntimeError("GridCraft launcher icon does not match approved uploaded Gc artwork")
    icon = Image.open(explicit).convert("RGBA")
    # Owner icon palette: dark green #006818 background, lime #ABE880 Gc.
    # Red channel is 0 on the background, ~171 on lettering, so the glyph
    # alpha mask preserves antialiasing without retaining the rounded tile.
    alpha = icon.getchannel("R").point(lambda red: min(255, round(red * 255 / 171)))
    from PIL import ImageChops
    alpha = ImageChops.multiply(alpha, icon.getchannel("A"))
    letters = Image.new("RGBA", icon.size, (171, 232, 128, 0))
    letters.putalpha(alpha)
    bounds = letters.getbbox()
    if not bounds:
        raise RuntimeError("Approved GridCraft Gc artwork has no readable lettering")
    letters = letters.crop(bounds)
    factor = min(ARTWORK_PX / letters.width, ARTWORK_PX / letters.height)
    letters = letters.resize((max(1, round(letters.width * factor)),
                              max(1, round(letters.height * factor))), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_PX, CANVAS_PX), (0, 0, 0, 0))
    canvas.paste(letters, ((CANVAS_PX - letters.width) // 2,
                           (CANVAS_PX - letters.height) // 2), letters)
    out = res_dir / "drawable-xxxhdpi" / "ic_launcher_foreground.png"
    canvas.save(out)
    (res_dir / "drawable" / "ic_launcher_background.xml").write_text(
        _BG_XML.format(color="#006818")
    )
    print("GridCraft Gc icon: owner artwork, centered letters, solid green adaptive background; no double mask")
    return chosen
