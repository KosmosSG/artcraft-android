"""Inspect the actual packaged adaptive layer and export mask previews."""
from pathlib import Path
from PIL import Image, ImageDraw
import io, sys, zipfile
apk, builder, dest = map(Path, sys.argv[1:])
files = list(builder.rglob('drawable-xxxhdpi/ic_launcher_foreground.png'))
assert len(files) == 1, files
expected = Image.open(files[0]).convert('RGBA')
assert expected.size == (432, 432)
assert expected.getchannel('A').getextrema() == (255, 255), 'Inset alpha creates a second frame'
with zipfile.ZipFile(apk) as z:
    matched = False
    for name in z.namelist():
        if not name.startswith('res/') or not name.endswith('.png'): continue
        try: actual = Image.open(io.BytesIO(z.read(name))).convert('RGBA')
        except OSError: continue
        if actual.size == expected.size and actual.tobytes() == expected.tobytes():
            matched = True; break
    assert matched, 'Packaged adaptive foreground mismatch'
dest.mkdir(parents=True, exist_ok=True)
expected.save(dest / 'DeckCraft-packaged-adaptive-foreground.png')
visible = expected.crop((72, 72, 360, 360))
for label, radius in [('round', 144), ('rounded-square', 65)]:
    mask = Image.new('L', visible.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 287, 287), radius=radius, fill=255)
    preview = visible.copy(); preview.putalpha(mask)
    preview.save(dest / f'DeckCraft-launcher-{label}.png')
print('PASS: generated approved pixels match actual APK adaptive resource')
