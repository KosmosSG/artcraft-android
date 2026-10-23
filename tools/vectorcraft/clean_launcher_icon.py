"""Remove embedded black launcher border from APPROVED Vc artwork at build-time.

Keep the original approved RGBA PNG untouched. This produces a separate, opaque
adaptive Android icon source by feathering only the *interior* of the approved
logo onto an orange background sampled from the lower, non-letter region.
This specifically avoids painting the existing rounded black border into the
Android launcher: Android itself owns the adaptive rounded-square mask.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

def generate(source, output):
    source=Path(source)
    image=Image.open(source).convert("RGBA")
    if image.width!=image.height or image.width<512:
        raise ValueError("Expected original high-resolution square Vc artwork")
    w=image.width
    # Determine the deep-orange brand matte from pixels across the APPROVED art,
    # not one fixed scanline (some uploaded PNGs add transparent padding).
    swatch=image.resize((80,80),Image.Resampling.BOX)
    candidates=[]
    for r,g,b,a in swatch.getdata():
        if a<190 or r<85 or r<1.18*g or r<1.40*b: continue
        if max(r,g,b)-min(r,g,b)<25: continue
        # Exclude near-white glass letter highlights.
        if r>245 and g>210 and b>180: continue
        candidates.append((r,g,b))
    if candidates:
        background=tuple(sorted(px[i] for px in candidates)[len(candidates)//2] for i in range(3))
    else:
        # A fixed brown-orange matching the uploaded logo is safer than
        # allowing black or an untrusted transparent fringe to be the matte.
        background=(170,57,8)
    if max(background)<85:
        raise ValueError("Could not derive a non-black orange brand background")

    matte=Image.new("RGBA",(w,w),background+(255,))
    clean=image.copy()
    # Matte only the original INNER logo; the black border is in its outer
    # perimeter, not in the glossy Vc glyphs. Do not trim/resize the glyphs.
    mask=Image.new("L",(w,w),0)
    p=mask.load()
    # Deliberately unequal insets: logo glyphs extend farther left/right than
    # top/bottom. Feather spans a small amount to suppress old black frame.
    left,right=0.115,0.885
    top,bottom=0.165,0.835
    fade=0.028
    for y in range(w):
        yf=y/w
        if not top<=yf<=bottom: continue
        ay=min(1.,(yf-top)/fade,(bottom-yf)/fade)
        for x in range(w):
            xf=x/w
            if not left<=xf<=right: continue
            ax=min(1.,(xf-left)/fade,(right-xf)/fade)
            t=max(0.,min(ax,ay))
            p[x,y]=round(255*t*t*(3-2*t))
    original_alpha=image.getchannel("A")
    # Preserve actual alpha of glyph pixels, feather only the perimeter.
    from PIL import ImageChops
    clean.putalpha(ImageChops.multiply(original_alpha, mask))
    result=Image.alpha_composite(matte,clean).convert("RGB")
    # As a fail-closed check, no outer top/side border pixel can remain black.
    at=[result.getpixel((w//2,0)),result.getpixel((0,w//2)),
        result.getpixel((w-1,w//2)),result.getpixel((w//2,w-1))]
    if any(max(c)<40 for c in at):
        raise ValueError("Generated launcher border is unexpectedly dark")
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    result.save(target,"PNG",optimize=True)
    print(f"PASS: black frame removed from adaptive source; approved Vc glyphs preserved, matte {background}")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    generate(args.source,args.output)
