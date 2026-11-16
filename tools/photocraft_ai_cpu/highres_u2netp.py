#!/usr/bin/env python3
"""Full-resolution RGB-preserving U2NetP alpha mask proxy, locally and opt-in only."""
from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Callable
from PIL import Image, ImageChops

MAX_PIXELS = 20_000_000
PROXY_PIXELS = 4_000_000
PROXY_SIDE = 1536
MAX_OUTPUT_BYTES = 96 * 1024 * 1024


def proxy_dimensions(width: int, height: int) -> tuple[int, int]:
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError("Full-resolution image exceeds 20 MP safety bound")
    if width * height <= PROXY_PIXELS:
        return width, height
    scale = min(PROXY_SIDE / max(width, height), (PROXY_PIXELS / (width * height)) ** 0.5)
    dims = max(1, int(width * scale)), max(1, int(height * scale))
    if dims[0] * dims[1] > PROXY_PIXELS:
        raise ValueError("Invalid bounded model proxy size")
    return dims


def process_high_resolution(source: Path, destination: Path,
                            infer: Callable[[Path, Path], None]) -> None:
    source, destination = Path(source), Path(destination)
    if not source.is_file() or source.is_symlink():
        raise ValueError("Missing or symlinked source")
    if destination.exists() or destination.is_symlink() or destination.resolve() == source.resolve():
        raise ValueError("Output must be new and distinct")
    if destination.suffix.lower() != ".png":
        raise ValueError("Output must be a PNG")
    with Image.open(source) as original:
        if original.format != "PNG":
            raise ValueError("Only PNG input accepted")
        original.load()
        width, height = original.size
        if width * height <= PROXY_PIXELS:
            raise ValueError("Small images must use the owner-verified direct inference")
        proxy_size = proxy_dimensions(width, height)
        with tempfile.TemporaryDirectory(prefix="photocraft-ai-proxy-") as d:
            proxy_in, proxy_out = Path(d)/"in.png", Path(d)/"out.png"
            original.convert("RGB").resize(proxy_size, Image.Resampling.LANCZOS).save(
                proxy_in, format="PNG", compress_level=1
            )
            infer(proxy_in, proxy_out)
            if proxy_out.is_symlink() or not proxy_out.is_file() or proxy_out.stat().st_size > 24 * 1024 * 1024:
                raise ValueError("Invalid AI proxy result")
            with Image.open(proxy_out) as processed:
                if processed.format != "PNG" or processed.mode not in ("RGBA", "LA"):
                    raise ValueError("AI proxy output requires PNG alpha")
                processed.load()
                if processed.size != proxy_size:
                    raise ValueError("AI proxy dimensions mismatch")
                mask = processed.getchannel("A").resize((width, height), Image.Resampling.LANCZOS)
            result = original.convert("RGBA")
            result.putalpha(ImageChops.multiply(result.getchannel("A"), mask))
            if result.getchannel("A").getextrema()[1] == 0:
                raise ValueError("U2NetP produced an entirely transparent result")
            try:
                with destination.open("xb") as output:
                    result.save(output, "PNG", compress_level=1)
                if destination.stat().st_size > MAX_OUTPUT_BYTES:
                    raise ValueError("Full-size alpha PNG exceeds 96 MiB")
            except Exception:
                destination.unlink(missing_ok=True)
                raise
