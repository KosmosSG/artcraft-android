#!/usr/bin/env python3
"""Inspect APK contents without changing signatures or editing release artifacts.

Usage:
  python3 tools/android_apk_size_audit.py path/to/app.apk --arm64-only \
      --baseline-bytes 256640934 --max-growth-percent 3

This is an analysis and regression gate, not an optimizer. It avoids the
dangerous unzip/rezip shortcut which can break Android native library alignment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def inspect_apk(apk: Path, arm64_only: bool) -> dict:
    if not apk.is_file() or apk.stat().st_size <= 0:
        raise ValueError("APK is missing or empty")
    categories = {"native": 0, "assets": 0, "resources": 0, "other": 0}
    packed_categories = dict.fromkeys(categories, 0)
    native_architectures = set()
    largest = []
    with zipfile.ZipFile(apk) as archive:
        if archive.testzip() is not None:
            raise ValueError("APK ZIP failed integrity validation")
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = entry.filename
            if name.startswith("lib/") and name.endswith(".so"):
                category = "native"
                native_architectures.add(name.split("/")[1])
            elif name.startswith("assets/"):
                category = "assets"
            elif name.startswith("res/") or name in ("resources.arsc", "classes.dex"):
                category = "resources"
            else:
                category = "other"
            categories[category] += entry.file_size
            packed_categories[category] += entry.compress_size
            largest.append((entry.file_size, entry.compress_size, name))
    if arm64_only and native_architectures != {"arm64-v8a"}:
        raise ValueError(f"Expected ARM64-only native code, found {sorted(native_architectures)}")
    return {
        "apk": str(apk),
        "bytes": apk.stat().st_size,
        "sha256": sha256(apk),
        "native_architectures": sorted(native_architectures),
        "uncompressed_bytes_by_category": categories,
        "compressed_bytes_by_category": packed_categories,
        "largest_entries": [
            {"name": name, "uncompressed": size, "compressed": packed}
            for size, packed, name in sorted(largest, reverse=True)[:15]
        ],
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path)
    parser.add_argument("--arm64-only", action="store_true")
    parser.add_argument("--baseline-bytes", type=int)
    parser.add_argument("--max-growth-percent", type=float, default=3.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.max_growth_percent < 0:
        parser.error("--max-growth-percent must be non-negative")
    result = inspect_apk(args.apk, args.arm64_only)
    if args.baseline_bytes is not None:
        if args.baseline_bytes <= 0:
            parser.error("--baseline-bytes must be positive")
        delta = (result["bytes"] / args.baseline_bytes - 1) * 100
        result["growth_percent"] = round(delta, 2)
        result["baseline_bytes"] = args.baseline_bytes
        result["size_budget_passed"] = delta <= args.max_growth_percent
    print(json.dumps(result, indent=2))
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    if result.get("size_budget_passed") is False:
        raise SystemExit("APK exceeds configured growth budget; review before release")


if __name__ == "__main__":
    main()
