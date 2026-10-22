"""Original code-drawn glass Dc icon; no Adobe artwork or bundled font assets."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys


def draw_icon(path):
    size = 1024
    # Keep the complete tile opaque: Android applies the rounded icon mask.
    # A uniform edge colour also avoids seams in the builder's adaptive layers.
    image = Image.new('RGBA', (size, size), (76, 8, 45, 255))
    glow = Image.new('RGBA', image.size)
    g = ImageDraw.Draw(glow)
    # Keep the pink glass glow in the centre, away from the solid outer edge.
    g.ellipse((200, 120, 824, 904), fill=(247, 72, 190, 125))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(72)))
    glass = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(glass)
    draw.rounded_rectangle((120, 120, 904, 904), radius=180, fill=(250, 210, 255, 30), outline=(255, 220, 255, 150), width=3)
    draw.arc((145, 135, 875, 880), 190, 286, fill=(255, 225, 255, 220), width=5)
    image = Image.alpha_composite(image, glass)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 410)
    draw.text((512, 500), 'Dc', font=font, anchor='mm', fill=(255, 184, 230, 255), stroke_width=1)
    # Do not pre-clip to a rounded square. Modern Android launchers apply
    # their own adaptive mask; transparent PNG corners produce dark borders.
    image.save(path)


if __name__ == '__main__':
    draw_icon(sys.argv[1])
