from pathlib import Path
from PIL import Image, ImageDraw
import sys

def install(builder, prepared_icon):
    destination = Path(builder) / "source/vectorcraft/assets/app-icon/hicolor/128x128/apps/ai.storyteller.vectorcraft.png"
    if not destination.exists() or Image.open(destination).size != (128,128):
        raise ValueError("Pinned upstream VectorCraft brand image changed")
    image = Image.open(prepared_icon).convert("RGBA")
    if image.width != image.height or image.width < 512:
        raise ValueError("Approved Vc icon must be a large square")
    image = image.resize((128,128),Image.Resampling.LANCZOS)
    alpha = Image.new("L",(128,128),0)
    ImageDraw.Draw(alpha).rounded_rectangle((0,0,127,127),radius=23,fill=255)
    image.putalpha(alpha)
    image.save(destination,format="PNG")
    print("PASS: Android top-left UI mark now uses approved Vc artwork")

if __name__ == "__main__":
    install(sys.argv[1],sys.argv[2])
