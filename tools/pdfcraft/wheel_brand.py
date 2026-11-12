from pathlib import Path
import base64, hashlib, io, sys
from PIL import Image
png = base64.b64decode(Path(__file__).with_name('pc-icon.b64').read_text().strip(), validate=True)
assert hashlib.sha256(png).hexdigest() == '690439cf43b99f6d5e5f233f2cbb55877cfbe089e823ae2de600035884d5a3f8'
im = Image.open(io.BytesIO(png)).convert('RGBA')
mask = Image.new('L', im.size)
for y in range(im.height):
    for x in range(im.width):
        _,g,b,a = im.getpixel((x,y))
        mask.putpixel((x,y),int(max(0,min(1,max((g-14)/166,b/176)))*a))
bbox=mask.getbbox()
assert bbox
mask=mask.crop(bbox).resize((192,120), Image.Resampling.LANCZOS)
mark=Image.new('RGBA',(192,120),(251,180,176,0));mark.putalpha(mask)
Path(sys.argv[1]).write_bytes(mark.tobytes())
