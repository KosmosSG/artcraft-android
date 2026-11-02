#!/usr/bin/env python3
"""Explicit local PhotoCraft -> U2NetP CPU sidecar experiment.

Only accepts a pre-exported local image. Does NOT access PhotoCraft documents,
run a server, enable Android menu actions or write to an existing output.
No model download is permitted by this bridge.
"""
from __future__ import annotations
import argparse
import io
import json
import os
import stat
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
    if not source.is_file():
        raise ValueError("Input missing or too large")
    if destination.exists() or destination.suffix.lower() != ".png":
        raise ValueError("Output must be a new PNG path")
    if not destination.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    # The worker must consume the exact PNG snapshot validated for this
    # consenting operation, even if the original pathname changes.
    # A private input also prevents a surviving worker from reading a
    # different file after the original was checked.
    with tempfile.TemporaryDirectory(
        prefix="photocraft-ai-stage-", dir=destination.parent
    ) as stage_dir:
        staged_input = Path(stage_dir) / "input.png"
        staged_output = Path(stage_dir) / "result.png"
        try:
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as input_file:
                info = os.fstat(input_file.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
                    raise ValueError("Input missing or too large")
                input_snapshot = input_file.read(MAX_INPUT_BYTES + 1)
        except OSError as exc:
            raise ValueError("Input missing or unreadable") from exc
        if not input_snapshot or len(input_snapshot) > MAX_INPUT_BYTES:
            raise ValueError("Input missing or too large")
        try:
            with Image.open(io.BytesIO(input_snapshot)) as image:
                if image.format != "PNG":
                    raise ValueError("Only PNG input is accepted")
                width, height = image.size
                if width < 1 or height < 1 or width * height > MAX_PIXELS:
                    raise ValueError("Input dimensions outside safety limit")
                image.verify()
            # Chunk CRC validation alone does not decode IDAT pixels.
            with Image.open(io.BytesIO(input_snapshot)) as decoded:
                decoded.load()
                if decoded.size != (width, height):
                    raise ValueError("Decoded PNG dimensions changed")
        except Image.DecompressionBombError as exc:
            raise ValueError("Input dimensions outside safety limit") from exc
        with staged_input.open("xb") as private_input:
            private_input.write(input_snapshot)
        # Run inference into the private same-filesystem stage, with no
        # model-download permission and no captured image/subprocess logs.
        completed = subprocess.run(
            [sys.executable, str(BENCHMARK), "--run",
             "--input", str(staged_input), "--output", str(staged_output)],
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
        # Snapshot the exact bounded bytes through a no-follow descriptor.
        # Path validation followed by os.link(staged_output, ...) still had a
        # race: a worker's surviving child could replace the staged file
        # after validation and before the link, publishing different bytes.
        try:
            fd = os.open(staged_output, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as staged_file:
                info = os.fstat(staged_file.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_size > MAX_INPUT_BYTES):
                    raise RuntimeError("U2NetP output must be a bounded regular PNG file")
                snapshot = staged_file.read(MAX_INPUT_BYTES + 1)
            if not snapshot or len(snapshot) > MAX_INPUT_BYTES:
                raise RuntimeError("U2NetP output must be a bounded regular PNG file")
        except OSError as exc:
            raise RuntimeError("U2NetP output must be a regular PNG file") from exc
        from validate_output_png import inspect_bytes
        try:
            alpha = inspect_bytes(snapshot, width, height)
        except Exception as exc:
            raise RuntimeError("U2NetP output failed full PNG validation") from exc
        # Publish only a private copy of those validated bytes, created AFTER
        # the worker has returned in a new directory never passed to it.
        # The exclusive hard link cannot overwrite an existing destination;
        # the original worker path may change without changing this snapshot.
        with tempfile.TemporaryDirectory(
            prefix="photocraft-ai-verified-", dir=destination.parent
        ) as verified_dir:
            verified_output = Path(verified_dir) / "result.png"
            with verified_output.open("xb") as verified_file:
                verified_file.write(snapshot)
            try:
                os.link(verified_output, destination, follow_symlinks=False)
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
