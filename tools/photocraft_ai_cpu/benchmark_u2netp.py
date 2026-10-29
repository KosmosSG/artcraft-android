#!/usr/bin/env python3
"""Isolated PhotoCraft AI Phase-2 CPU benchmark: U2NetP via rembg/ONNX Runtime.

No PhotoCraft/ComfyUI modifications. Never uploads input images or prompts.
The ONNX model is downloaded ONLY with explicit --allow-model-download.
Writes only a new .png output with exclusive creation; never overwrites inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

MODEL_FILENAME = "u2netp.onnx"
# Integrity reference from rembg's U2NetP session. Model licensing must
# still be reviewed independently before commercial redistribution/use.
MODEL_MD5 = "8e83ca70e441ab06c318d82300c84806"
MAX_PIXELS = 4_000_000
MAX_INPUT_BYTES = 24 * 1024 * 1024
CPU_THREADS = 2


def model_directory() -> Path:
    value = os.environ.get("U2NET_HOME")
    if value:
        return Path(value).expanduser()
    # rembg model cache default as of rembg 2.0.78
    return Path(os.environ.get("XDG_DATA_HOME", "~")).expanduser() / ".u2net"


def model_integrity(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "not installed"
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != MODEL_MD5:
        return False, "file checksum differs from upstream rembg U2NetP reference"
    return True, "checksum matches upstream rembg reference"


def validate_image_shape(width: int, height: int) -> None:
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ValueError(f"Image dimensions exceed the {MAX_PIXELS:,}-pixel safety limit")


def output_location(input_file: Path | None, proposed: Path | None) -> Path:
    if proposed is None:
        directory = Path.home() / "Pictures" / "PhotoCraft-AI-Tests"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = f"u2netp-{stamp}-{os.getpid()}.png"
        result = directory / name
    else:
        result = proposed.expanduser()
    if result.suffix.lower() != ".png":
        raise ValueError("Output must be a .png file to retain transparency")
    if input_file is not None and input_file.expanduser().resolve() == result.resolve():
        raise ValueError("Output cannot overwrite the original input file")
    if result.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {result}")
    return result


def print_environment() -> bool:
    print("PhotoCraft AI isolated U2NetP CPU benchmark (NOT a PhotoCraft plugin)")
    print("Architecture:", platform.machine(), "Python:", sys.version.split()[0])
    print("Model path:", model_directory() / MODEL_FILENAME)
    ok, message = model_integrity(model_directory() / MODEL_FILENAME)
    print("Model:", message)
    print("ComfyUI/PyTorch environment: untouched")
    try:
        import onnxruntime as ort
        from PIL import Image
        import rembg
        providers = ort.get_available_providers()
        print("ONNX Runtime:", ort.__version__, "available providers:", providers)
        print("Pillow:", getattr(Image, "__version__", "installed"))
        if "CPUExecutionProvider" not in providers:
            print("ERROR: CPUExecutionProvider unavailable")
            return False
        print("rembg import: OK; model remains explicitly U2NetP (not a default model)")
        return True
    except ImportError as exc:
        print(f"Dependencies missing: {exc}")
        print('Install separately: python -m pip install --only-binary=:all: "rembg[cpu]==2.0.78" "onnxruntime==1.28.0"')
        return False


def benchmark(input_file: Path | None, output_file: Path | None,
              allow_download: bool) -> int:
    # Lock CPU usage before importing ONNX Runtime or rembg.
    os.environ["OMP_NUM_THREADS"] = str(CPU_THREADS)
    os.environ["OPENBLAS_NUM_THREADS"] = str(CPU_THREADS)
    os.environ["MKL_NUM_THREADS"] = str(CPU_THREADS)
    if platform.machine().lower() not in ("aarch64", "arm64", "x86_64"):
        print("WARNING: untested architecture; proceeding in CPU-only mode")
    model_file = model_directory() / MODEL_FILENAME
    good, status = model_integrity(model_file)
    if model_file.exists() and not good:
        raise RuntimeError(f"Refusing unverified model: {status}")
    if not good and not allow_download:
        raise RuntimeError(
            "U2NetP model is not present. Nothing downloaded. "
            "Review licensing, then explicitly rerun with --allow-model-download."
        )
    from PIL import Image, ImageDraw, ImageOps
    import onnxruntime as ort
    from rembg import new_session, remove
    providers = ort.get_available_providers()
    if "CPUExecutionProvider" not in providers:
        raise RuntimeError("CPUExecutionProvider is unavailable")
    if input_file is None:
        # Transparent-cutout accuracy on synthetic shapes is NOT a quality
        # benchmark; this only verifies local inference and memory consumption.
        img = Image.new("RGB", (512, 512), "#f4f4ee")
        draw = ImageDraw.Draw(img)
        draw.ellipse((110, 80, 410, 465), fill="#355aa0")
        print("Input: synthetic 512x512 test image (no user content)")
    else:
        input_file = input_file.expanduser()
        if not input_file.is_file():
            raise FileNotFoundError(f"Image missing: {input_file}")
        if input_file.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError(f"Input image exceeds {MAX_INPUT_BYTES // (1024*1024)} MiB cap")
        with Image.open(input_file) as source:
            validate_image_shape(*source.size)
            img = ImageOps.exif_transpose(source).convert("RGB")
        print("Input dimensions:", img.size, "(filename omitted)")
    validate_image_shape(*img.size)
    destination = output_location(input_file, output_file)

    options = ort.SessionOptions()
    options.intra_op_num_threads = CPU_THREADS
    options.inter_op_num_threads = 1
    started = time.monotonic()
    session = new_session(
        "u2netp",
        sess_opts=options,
        providers=["CPUExecutionProvider"],
    )
    init_seconds = time.monotonic() - started
    good, status = model_integrity(model_file)
    if not good:
        raise RuntimeError(f"U2NetP integrity check failed after session load: {status}")
    active_providers = session.inner_session.get_providers()
    if active_providers != ["CPUExecutionProvider"]:
        raise RuntimeError(f"Unexpected inference provider: {active_providers}")
    inference_start = time.monotonic()
    result = remove(img, session=session)
    inference_seconds = time.monotonic() - inference_start
    if not isinstance(result, Image.Image):
        raise RuntimeError("Inference did not produce a Pillow image")
    if result.size != img.size:
        raise RuntimeError("Inference output dimensions do not match input")
    result = result.convert("RGBA")
    bounds = result.getchannel("A").getextrema()
    if bounds == (0, 0):
        raise RuntimeError("Inference generated a completely transparent output")
    # Entire image must fit in memory/encoded bytes before creating a new file.
    payload = io.BytesIO()
    result.save(payload, format="PNG", optimize=False)
    if payload.tell() > MAX_INPUT_BYTES:
        raise RuntimeError("Output exceeds 24 MiB safe test size")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(payload.getvalue())

    rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({
        "status": "cpu_test_completed",
        "model": "u2netp",
        "providers": active_providers,
        "dimensions": list(img.size),
        "model_load_seconds": round(init_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "peak_process_rss_mib_linux": round(rss_kib / 1024, 1),
        "alpha_range": list(bounds),
        "output": str(destination),
        "note": "Separate local PNG only; no PhotoCraft layers, upload or Undo integration",
    }, indent=2))
    return 0


def self_test() -> int:
    import tempfile
    old_home = os.environ.get("U2NET_HOME")
    try:
        with tempfile.TemporaryDirectory() as root:
            os.environ["U2NET_HOME"] = root
            assert model_directory() == Path(root)
            assert model_integrity(Path(root) / MODEL_FILENAME) == (False, "not installed")
            for pair in [(0, 20), (5000, 1000), (20, 0)]:
                try:
                    validate_image_shape(*pair)
                    raise AssertionError(f"Accepted invalid input {pair}")
                except ValueError:
                    pass
            validate_image_shape(512, 512)
            original = Path(root) / "original.png"
            original.write_bytes(b"example")
            try:
                output_location(original, original)
                raise AssertionError("Allowed overwriting input")
            except ValueError:
                pass
            try:
                output_location(None, original)
                raise AssertionError("Allowed overwriting an existing file")
            except FileExistsError:
                pass
            out = output_location(original, Path(root) / "new.png")
            assert out.name == "new.png" and not out.exists()
    finally:
        if old_home is None:
            os.environ.pop("U2NET_HOME", None)
        else:
            os.environ["U2NET_HOME"] = old_home
    print("PASS: no-dependency safety tests (paths, limits, no overwrite, no auto-download)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true", help="Run safe pure-Python tests; no model/deps required")
    group.add_argument("--check", action="store_true", help="Show runtime and model cache status; never downloads")
    group.add_argument("--run", action="store_true", help="Run local CPU inference, creating a NEW output PNG")
    p.add_argument("--input", type=Path, help="Optional local image path; defaults to synthetic 512x512 sample")
    p.add_argument("--output", type=Path, help="Optional new output PNG path; never overwrites")
    p.add_argument("--allow-model-download", action="store_true",
                   help="Explicitly allow first-time download of U2NetP weights from rembg's GitHub release")
    args = p.parse_args()
    if (args.input or args.output or args.allow_model_download) and not args.run:
        p.error("--input, --output and --allow-model-download require --run")
    if args.self_test:
        return self_test()
    if args.check:
        return 0 if print_environment() else 2
    return benchmark(args.input, args.output, args.allow_model_download)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
