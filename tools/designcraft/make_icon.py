"""Convert the owner's newly uploaded glossy Dc artwork to the pinned Android icon PNG.

The 192-pixel WebP is a high-quality launcher-size derivative of the owner's
1254-pixel image (original SHA-256
f6dbdba9ea8e510414934c0aea697457a922dfada96feecc0baf0809d8e391ae).
Do not regenerate branding or substitute other icons.
"""
from pathlib import Path
from PIL import Image
import hashlib
import sys

APPROVED_SHA256 = "306fb5fd3efdb138eee5d0b7c0c34b91718229c60408e92af4bba949daecea9d"
STAGED_PNG_SHA256 = "df27b2f46cfad9df7493ee88da9265fc7de2d62313361746d9bc0ecd5dd6803b"
SOURCE = Path(__file__).parent / "icon/dc-user-20261023.webp"

def draw_icon(path):
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != APPROVED_SHA256:
        raise ValueError("New owner-approved Dc icon checksum mismatch")
    with Image.open(SOURCE) as im:
        if im.format != "WEBP" or im.size != (192, 192):
            raise ValueError("Expected pinned owner-approved 192-pixel Dc packaging derivative")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGBA").save(destination, "PNG")
    if hashlib.sha256(destination.read_bytes()).hexdigest() != STAGED_PNG_SHA256:
        raise ValueError("Staged DesignCraft icon PNG differs from approved uploaded artwork")

if __name__ == "__main__":
    draw_icon(sys.argv[1])
