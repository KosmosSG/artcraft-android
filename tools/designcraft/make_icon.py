"""Original code-drawn glass Dc icon; no Adobe artwork or bundled font assets."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import sys


def draw_icon(path):
    size = 1024
    image = Image.new('RGBA', (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / size
        draw.line((0, y, size, y), fill=(int(48+65*t), int(10+8*t), int(80+64*t), 255))
    glow = Image.new('RGBA', image.size)
    g = ImageDraw.Draw(glow)
    g.ellipse((120, -240, 1050, 650), fill=(247, 72, 190, 160))
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(100)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((120, 120, 904, 904), radius=180, fill=(250, 210, 255, 30), outline=(255, 220, 255, 150), width=3)
    draw.arc((145, 135, 875, 880), 190, 286, fill=(255, 225, 255, 220), width=5)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 410)
    draw.text((512, 500), 'Dc', font=font, anchor='mm', fill=(255, 184, 230, 255), stroke_width=1)
    mask = Image.new('L', image.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 1023, 1023), radius=225, fill=255)
    image.putalpha(mask)
    image.save(path)


if __name__ == '__main__':
    draw_icon(sys.argv[1])
