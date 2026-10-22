"""Stage exact user-approved Dc PNG; never synthesize replacement artwork."""
from pathlib import Path
import hashlib
import shutil
import struct
import sys

APPROVED_SHA256 = "92070af3f08464e65a03eb181a0ccc97c29f131404476649410bfb417560c67f"
SOURCE = Path(__file__).parent / "icon/dc-user-approved.png"

def draw_icon(path):
    data = SOURCE.read_bytes()
    if hashlib.sha256(data).hexdigest() != APPROVED_SHA256:
        raise ValueError("DesignCraft approved artwork checksum mismatch")
    if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (1254, 1254):
        raise ValueError("Expected original 1254x1254 DesignCraft PNG")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, destination)
    if destination.read_bytes() != data:
        raise ValueError("DesignCraft icon transfer changed the approved bytes")

if __name__ == "__main__":
    draw_icon(sys.argv[1])
