#!/usr/bin/env python3
"""Explicit local PhotoCraft -> U2NetP CPU sidecar experiment.

Only accepts a pre-exported local image. Does NOT access PhotoCraft documents,
run a server, enable Android menu actions or write to an existing output.
No model download is permitted by this bridge.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
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
    destination = output_path.expanduser().resolve()
    if source == destination:
        raise ValueError("Input and output cannot be identical")
    if not source.is_file() or source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input missing or too large")
    if destination.exists() or destination.suffix.lower() != ".png":
        raise ValueError("Output must be a new PNG path")
    if not destination.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    with Image.open(source) as image:
        if image.format != "PNG":
            raise ValueError("Only PNG input is accepted")
        width, height = image.size
        if width < 1 or height < 1 or width * height > MAX_PIXELS:
            raise ValueError("Input dimensions outside safety limit")
        image.verify()
    # Use the already-verified U2NetP model only; never pass download consent.
    # Do not capture the image or raw result in logs.
    completed = subprocess.run(
        [sys.executable, str(BENCHMARK), "--run",
         "--input", str(source), "--output", str(destination)],
        check=False, timeout=180, capture_output=True, text=True,
    )
    if completed.returncode != 0:
        # The benchmark may have produced an incomplete output; never import it.
        raise RuntimeError("U2NetP subprocess failed; inspect isolated benchmark logs")
    from validate_output_png import inspect
    try:
        alpha = inspect(destination, width, height)
    except Exception:
        # Preserve output for diagnosis; never claim it is safe to import.
        raise RuntimeError("U2NetP output failed full PNG validation")
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
