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
    """Validate one immutable file snapshot, not a mutable pathname.

    The old is_file()/stat()/Image.open() sequence could follow a hard link
    or block on a FIFO swapped in after the check. Open without following
    symlinks or blocking on special files, then validate the same bytes read
    from the checked regular, single-link descriptor.
    """
    import os
    import stat
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError("Invalid expected image dimensions")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as image_file:
            info = os.fstat(image_file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_size > MAX_BYTES):
                raise ValueError("Missing, aliased or oversized PNG")
            payload = image_file.read(MAX_BYTES + 1)
    except OSError:
        # Do not disclose local filesystem paths in caller-facing errors.
        raise ValueError("Missing, aliased or unreadable PNG") from None
    return inspect_bytes(payload, width, height)

def inspect_bytes(payload: bytes, width: int, height: int) -> tuple[int, int]:
    """Validate the exact bounded bytes that the HTTP server will return.

    Unlike a path-based validation followed by a separate read, this cannot
    inspect one PNG and then accidentally return a different file after a
    rename, symlink swap, or immediate inode reuse in the staging directory.
    """
    import io
    from PIL import Image, ImageFile
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError("Invalid expected image dimensions")
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError("Missing or oversized PNG bytes")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with Image.open(io.BytesIO(payload)) as image:
        if image.format != "PNG" or image.size != (width, height):
            raise ValueError("Unexpected format or dimensions")
        if image.mode not in ("RGBA", "LA"):
            raise ValueError("PNG must contain an alpha channel")
        image.verify()
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        if image.size != (width, height) or image.mode not in ("RGBA", "LA"):
            raise ValueError("Decoded image properties changed")
        low, high = image.getchannel("A").getextrema()
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
        assert inspect_bytes(path.read_bytes(), 16, 12) == (200, 200)
        alias = Path(directory) / "alias.png"
        alias.symlink_to(path)
        try:
            inspect(alias, 16, 12)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted symlinked output PNG")
        # A hard link is not a symlink and would pass the old is_file()
        # check; reject it before any bytes are inspected.
        import os
        hardlink = Path(directory) / "hardlink.png"
        os.link(path, hardlink)
        try:
            inspect(hardlink, 16, 12)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted hard-linked output PNG")
        hardlink.unlink()
        # A FIFO must not block a local test indefinitely while waiting
        # for a writer, even if swapped in after a preliminary path check.
        if hasattr(os, "mkfifo"):
            fifo = Path(directory) / "fifo.png"
            os.mkfifo(fifo)
            try:
                inspect(fifo, 16, 12)
            except ValueError:
                pass
            else:
                raise AssertionError("Accepted FIFO output PNG")
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
