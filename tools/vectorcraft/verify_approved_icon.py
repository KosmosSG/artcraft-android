"""Check the exact user-approved VectorCraft launcher PNG before APK packaging.

The approved image is a 1254x1254 RGBA PNG. Reject any differently encoded,
cropped, resized or substituted artwork: release builds must use the original
uploaded bytes, not a visually similar icon or an outdated repository asset.
"""
from pathlib import Path
import hashlib
import struct
import sys

APPROVED_SHA256 = "291c7768cabaf4419082abfbd100a17668e9c7c4ca8a57fa45667f0f7233dbc2"
APPROVED_SIZE = (1254, 1254)


def verify(path: Path) -> None:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != APPROVED_SHA256:
        raise ValueError("VectorCraft icon does not match the user's approved PNG checksum")
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("VectorCraft icon is not a PNG")
    if struct.unpack(">II", data[16:24]) != APPROVED_SIZE:
        raise ValueError("VectorCraft icon must be the approved 1254x1254 PNG")
    if data[25] != 6:  # PNG color type 6 = RGBA.
        raise ValueError("VectorCraft icon must preserve RGBA mode")


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]))
    except (ValueError, OSError, IndexError) as exc:
        raise SystemExit(f"Approved VectorCraft icon unavailable: {exc}")
    print("Verified original approved VectorCraft launcher PNG")
