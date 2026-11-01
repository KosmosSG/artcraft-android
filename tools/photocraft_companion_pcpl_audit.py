#!/usr/bin/env python3
"""Read-only PhotoCraft Companion .pcpl audit; NEVER installs or executes plugins.

This is a pre-port compatibility gate, not an Android plugin runtime.
"""
from __future__ import annotations

import argparse
import json
import re
import stat
import sys
import zipfile
from pathlib import Path

MAX_ARCHIVE_BYTES = 512 * 1024
MAX_ENTRIES = 64
MAX_MEMBER_BYTES = 128 * 1024
MAX_TOTAL_UNPACKED_BYTES = 1024 * 1024
MAX_COMPRESSION_RATIO = 250
KNOWN_TYPES = frozenset({
    "no_code", "native_ai", "native_algorithm", "interactive_ui",
    "script", "external_cli", "dynamic_lib",
})
# Metadata-only source and artwork; no code or model binaries ever imported.
ALLOWED_SUFFIXES = frozenset({".json", ".svg", ".md", ".txt", ".rhai"})
ALLOWED_EXACT_NAMES = frozenset({"LICENSE", "LICENSE-MIT", "NOTICE"})
PLUGIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")
VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:-[0-9A-Za-z.-]+)?$")


class AuditError(ValueError):
    """Fail-closed plugin-package validation error."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    output = {}
    for key, value in pairs:
        if key in output:
            raise AuditError("duplicate JSON key: " + key)
        output[key] = value
    return output


def _bad_constant(value: str) -> None:
    raise AuditError("nonstandard JSON constant: " + value)


def _safe_zip_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    if (
        not name or len(name) > 240 or name.startswith("/")
        or "\\" in name or ":" in name
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or any(part in ("", ".", "..") for part in name.split("/"))
    ):
        raise AuditError("unsafe ZIP member path")
    if info.is_dir() or info.flag_bits & 1:
        raise AuditError("directory or encrypted ZIP member")
    kind = stat.S_IFMT(info.external_attr >> 16)
    if kind not in (0, stat.S_IFREG):
        raise AuditError("non-regular ZIP member")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise AuditError("unsupported ZIP compression method")
    if info.file_size > MAX_MEMBER_BYTES:
        raise AuditError("oversized ZIP member")
    if info.file_size > max(info.compress_size, 1) * MAX_COMPRESSION_RATIO:
        raise AuditError("excessive ZIP compression ratio")
    if info.filename.rsplit("/", 1)[-1] not in ALLOWED_EXACT_NAMES:
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            raise AuditError("executable, model, or unsupported file in package")


def _field_text(manifest: dict, key: str, limit: int) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AuditError("invalid plugin manifest field: " + key)
    if any(ord(char) < 32 for char in value):
        raise AuditError("control character in manifest: " + key)
    return value


def _manifest(content: bytes) -> dict:
    try:
        value = json.loads(
            content.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_bad_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuditError("invalid UTF-8 JSON manifest") from exc
    if not isinstance(value, dict):
        raise AuditError("manifest must be a JSON object")

    plugin_id = _field_text(value, "id", 128)
    name = _field_text(value, "name", 120)
    version = _field_text(value, "version", 48)
    plugin_type = _field_text(value, "plugin_type", 48)
    if not PLUGIN_ID.fullmatch(plugin_id):
        raise AuditError("invalid plugin id")
    if not VERSION.fullmatch(version):
        raise AuditError("invalid plugin version")
    if plugin_type not in KNOWN_TYPES:
        raise AuditError("unknown plugin type: " + plugin_type)
    for key in ("commands", "post_commands", "sub_actions", "models"):
        entries = value.get(key, [])
        if not isinstance(entries, list) or len(entries) > 64:
            raise AuditError("invalid manifest collection: " + key)
    return {
        "id": plugin_id,
        "name": name,
        "version": version,
        "plugin_type": plugin_type,
        "has_commands": bool(value.get("commands") or value.get("post_commands")),
        "declares_models": bool(value.get("models")),
    }


def inspect_pcpl(path: Path) -> dict:
    """No extraction, network access, subprocess, installation, or execution."""
    if not path.is_file() or path.is_symlink():
        raise AuditError("package must be a regular, non-symlinked file")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise AuditError("oversized .pcpl archive")
    if path.suffix.lower() != ".pcpl":
        raise AuditError("expected a .pcpl archive")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ENTRIES:
                raise AuditError("invalid number of archive members")
            names = set()
            total = 0
            for info in infos:
                _safe_zip_member(info)
                if info.filename in names:
                    raise AuditError("duplicate ZIP member")
                names.add(info.filename)
                total += info.file_size
                if total > MAX_TOTAL_UNPACKED_BYTES:
                    raise AuditError("oversized total unpacked archive")
            manifests = [name for name in names if name.rsplit("/", 1)[-1] == "plugin.json"]
            if len(manifests) != 1:
                raise AuditError("expected exactly one plugin.json")
            root = manifests[0][:-len("plugin.json")]
            if any(not name.startswith(root) for name in names):
                raise AuditError("package mixes unrelated root paths")
            with archive.open(manifests[0]) as stream:
                manifest = _manifest(stream.read(MAX_MEMBER_BYTES + 1))
            # Consume every member to validate ZIP CRC and decompression behavior.
            for info in infos:
                with archive.open(info) as stream:
                    if len(stream.read(MAX_MEMBER_BYTES + 1)) != info.file_size:
                        raise AuditError("inconsistent ZIP member size")
    except (zipfile.BadZipFile, EOFError, RuntimeError, OSError) as exc:
        raise AuditError("malformed .pcpl ZIP archive") from exc
    return {
        "format": "photocraft-companion-pcpl",
        "catalog_status": "metadata_only",
        "execution_enabled": False,
        "installed": False,
        "network_used": False,
        "model_downloaded": False,
        "upstream_schema": "PhotoCraft Companion plugin.json (partial)",
        **manifest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="local .pcpl ZIP (never extracted)")
    args = parser.parse_args(argv)
    try:
        result = inspect_pcpl(args.archive)
    except AuditError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
