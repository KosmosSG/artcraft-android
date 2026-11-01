#!/usr/bin/env python3
"""Explicit local PhotoCraft -> U2NetP CPU sidecar experiment.

Only accepts a pre-exported local image. Does NOT access PhotoCraft documents,
run a server, enable Android menu actions or write to an existing output.
No model download is permitted by this bridge.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent
BENCHMARK = HERE / "benchmark_u2netp.py"
MAX_INPUT_BYTES = 24 * 1024 * 1024
MAX_PIXELS = 4_000_000

def run(input_path: Path, output_path: Path, consent: bool) -> None:
    if not consent:
        raise ValueError("Explicit --consent-local-processing is required")
    source = input_path.expanduser().resolve(strict=True)
    # Path.resolve() follows even a dangling symlink. An output alias to a
    # not-yet-created PNG would otherwise pass exists() and let the model
    # write outside the path the consenting caller explicitly selected.
    # Reject the alias BEFORE resolving it; do not change the source file.
    requested_output = output_path.expanduser()
    if requested_output.is_symlink():
        raise ValueError("Output must be a new PNG path, not a symlink")
    destination = requested_output.resolve()
    if source == destination:
        raise ValueError("Input and output cannot be identical")
    if not source.is_file() or source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input missing or too large")
    if destination.exists() or destination.suffix.lower() != ".png":
        raise ValueError("Output must be a new PNG path")
    if not destination.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    try:
        with Image.open(source) as image:
            if image.format != "PNG":
                raise ValueError("Only PNG input is accepted")
            width, height = image.size
            if width < 1 or height < 1 or width * height > MAX_PIXELS:
                raise ValueError("Input dimensions outside safety limit")
            image.verify()
    except Image.DecompressionBombError as exc:
        # Pillow may reject an oversized IHDR during open(), before our own
        # 4 MP check. Surface a controlled validation error to the CLI.
        raise ValueError("Input dimensions outside safety limit") from exc
    # verify() checks PNG chunk CRCs but does not inflate image pixels.
    # Reject CRC-valid, corrupt IDAT streams before starting CPU inference.
    with Image.open(source) as decoded:
        decoded.load()
        if decoded.size != (width, height):
            raise ValueError("Decoded PNG dimensions changed")
    # Run inference into a private temporary directory on the SAME filesystem
    # as the requested output. A failed/timeout/invalid inference must not
    # leave a partial user-visible PNG. Do not pass model-download consent.
    # Never capture image data or arbitrary subprocess logs in memory.
    with tempfile.TemporaryDirectory(
        prefix="photocraft-ai-stage-", dir=destination.parent
    ) as stage_dir:
        staged_output = Path(stage_dir) / "result.png"
        completed = subprocess.run(
            [sys.executable, str(BENCHMARK), "--run",
             "--input", str(source), "--output", str(staged_output)],
            check=False, timeout=180,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise RuntimeError("U2NetP subprocess failed; no output committed")
        # A child process can replace its staged output with a symlink to
        # an unrelated local file. PNG validation follows that symlink, and
        # hard-link publication may expose it outside the private stage.
        # Only a regular file produced inside this private stage is allowed.
        if staged_output.is_symlink() or not staged_output.is_file():
            raise RuntimeError("U2NetP output must be a regular PNG file")
        from validate_output_png import inspect
        try:
            alpha = inspect(staged_output, width, height)
        except Exception as exc:
            raise RuntimeError("U2NetP output failed full PNG validation") from exc
        # An exclusive hard link publishes the validated bytes atomically.
        # Unlike rename/replace, it cannot overwrite a file or symlink created
        # at the destination after the initial preflight (TOCTOU protection).
        # Failure to link is fail-closed; temporary data is always removed.
        try:
            os.link(staged_output, destination)
        except FileExistsError as exc:
            raise ValueError("Output must be a new PNG path") from exc
    print(json.dumps({
        "status": "validated_local_output",
        "width": width, "height": height,
        "alpha_min": alpha[0], "alpha_max": alpha[1],
        "output": str(destination),
        "editor_integration": False,
        "note": "Standalone opt-in local file processing; no PhotoCraft layer insertion"
    }))

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--consent-local-processing", action="store_true")
    args = p.parse_args()
    run(args.input, args.output, args.consent_local_processing)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)
