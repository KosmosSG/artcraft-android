#!/usr/bin/env python3
"""Validate a local U2NetP RGBA PNG before any future PhotoCraft import.

This is a standalone test helper, NOT an Android image decoder or editor hook.
It never modifies source images, sends network requests or creates layers.
"""
from __future__ import annotations
import argparse
from pathlib import Path

MAX_BYTES = 24 * 1024 * 1024
MAX_PIXELS = 4_000_000

def inspect(path: Path, width: int, height: int) -> tuple[int, int]:
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError("Invalid expected image dimensions")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Missing or oversized PNG")
    from PIL import Image, ImageFile
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != (width, height):
            raise ValueError("Unexpected format or dimensions")
        if image.mode not in ("RGBA", "LA"):
            raise ValueError("PNG must contain an alpha channel")
        image.verify()
    # Reopen and force full pixel decode: verify() alone does not decode pixels.
    with Image.open(path) as image:
        image.load()
        if image.size != (width, height) or image.mode not in ("RGBA", "LA"):
            raise ValueError("Decoded image properties changed")
        alpha = image.getchannel("A")
        low, high = alpha.getextrema()
        if high == 0:
            raise ValueError("Output is entirely transparent")
        return low, high

def self_test() -> None:
    import tempfile
    from PIL import Image
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "test.png"
        Image.new("RGBA", (16, 12), (255, 0, 0, 200)).save(path)
        assert inspect(path, 16, 12) == (200, 200)
        for size in [(15, 12), (0, 12), (5000, 5000)]:
            try:
                inspect(path, *size)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Accepted invalid dimensions: {size}")
        Image.new("RGB", (16, 12), "red").save(path)
        try:
            inspect(path, 16, 12)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted PNG without alpha")
        path.write_bytes(b"not a PNG")
        try:
            inspect(path, 16, 12)
        except (ValueError, OSError):
            pass
        else:
            raise AssertionError("Accepted invalid PNG")
    print("PASS: local PNG fully decoded, alpha and dimensions validated")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.input is not None and args.width is not None and args.height is not None:
        print("Validated alpha range:", inspect(args.input, args.width, args.height))
    else:
        parser.error("Use --self-test or --input FILE --width N --height N")
