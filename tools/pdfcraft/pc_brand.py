"""Stage the user's supplied red Pc icon in the isolated PDFCraft TEST build only.

The base64 asset is a 256px losslessly palettized derivative of the uploaded
1000px PNG; it is never substituted into historical/published release files.
No effect on other apps. Called ONLY by the isolated PDFCraft workflow.
"""
import base64, hashlib, io, json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "tools/approved-branding/assets"
ICON = Path(__file__).with_name("pc-icon.b64")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def save(path: Path, im: Image.Image):
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", optimize=True)

def main():
    png = base64.b64decode(ICON.read_text().strip(), validate=True)
    assert digest(png) == "690439cf43b99f6d5e5f233f2cbb55877cfbe089e823ae2de600035884d5a3f8"
    icon = Image.open(io.BytesIO(png)).convert("RGBA")
    assert icon.size == (256,256)
    manifest_path = ASSETS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["app"] == "pdfcraft"
    master = ASSETS / manifest["filename"]
    master.write_bytes(png)
    manifest["source_sha256"] = digest(png)
    manifest["source_size"] = [256, 256]
    manifest["bg_color"] = "#FB0E00"
    # The supplied full-square image is for legacy launcher and top-left icon.
    # On adaptive launchers only the pink Pc glyph goes in the safe foreground.
    # Android draws the red background independently so no double masking occurs.
    alpha = Image.new("L", icon.size)
    green = icon.getchannel("G")
    blue = icon.getchannel("B")
    old_alpha = icon.getchannel("A")
    gp, bp, ap = green.load(), blue.load(), old_alpha.load()
    dest = alpha.load()
    for y in range(icon.height):
        for x in range(icon.width):
            intensity = max((gp[x,y] - 14)/166, bp[x,y]/176)
            dest[x,y] = int(max(0.0, min(1.0, intensity)) * ap[x,y])
    bbox = alpha.getbbox()
    assert bbox is not None
    glyph_mask = alpha.crop(bbox).resize((218, 135), Image.Resampling.LANCZOS)
    fg = Image.new("RGBA",(432,432),(0,0,0,0))
    letters = Image.new("RGBA", glyph_mask.size,(251,180,176,0))
    letters.putalpha(glyph_mask)
    fg.alpha_composite(letters, (107, 148))
    for key in manifest["resources"]:
        path = ASSETS / key
        if key.endswith("ic_launcher_foreground.png"):
            save(path, fg)
        elif key.endswith("ic_inapp_brand_128.png"):
            save(path, icon.resize((128,128),Image.Resampling.LANCZOS))
        elif key.endswith("ic_inapp_brand_64.png"):
            save(path, icon.resize((64,64),Image.Resampling.LANCZOS))
        elif key.endswith("ic_inapp_symbol_128.png"):
            save(path, fg.resize((128,128),Image.Resampling.LANCZOS))
        elif key.endswith("ic_inapp_symbol_64.png"):
            save(path, fg.resize((64,64),Image.Resampling.LANCZOS))
        elif key.endswith("ic_launcher.png") or key.endswith("ic_launcher_round.png"):
            size = Image.open(path).size
            save(path, icon.resize(size,Image.Resampling.LANCZOS))
        manifest["resources"][key] = digest(path.read_bytes())
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n")
    print("PDFCraft Pc icon staged in temporary branding assets only")

if __name__ == "__main__":
    main()
