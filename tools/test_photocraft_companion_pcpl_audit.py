#!/usr/bin/env python3
"""Offline negative regression tests for PhotoCraft Companion metadata-only audit."""
import io
import json
import os
import stat
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

import photocraft_companion_pcpl_audit as audit


MANIFEST = {
    "id": "macro.photocraft.plugins.black_and_white",
    "name": "B&W Film Pop",
    "version": "1.0.0",
    "plugin_type": "no_code",
    "commands": [
        {"command": "layer.duplicate", "params": {}},
        {"command": "image.adjustments.desaturate", "params": {}},
    ],
}


def packed(files, method=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buffer, "w", compression=method) as z:
            for name, value in files:
                if isinstance(value, zipfile.ZipInfo):
                    z.writestr(value, b"payload")
                else:
                    z.writestr(name, value)
    return buffer.getvalue()


class PcplAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sample.pcpl"

    def write(self, files):
        self.path.write_bytes(packed(files))
        return self.path

    def manifest(self, **changes):
        return json.dumps({**MANIFEST, **changes}).encode()

    def accept(self, files=None):
        self.write(files or [
            ("plugin.json", self.manifest()),
            ("icon.svg", b"<svg></svg>"),
            ("README.md", b"An upstream manifest example"),
        ])
        return audit.inspect_pcpl(self.path)

    def reject(self, files):
        self.write(files)
        with self.assertRaises(audit.AuditError):
            audit.inspect_pcpl(self.path)

    def test_valid_upstream_no_code_is_metadata_only(self):
        result = self.accept()
        self.assertEqual(result["plugin_type"], "no_code")
        self.assertEqual(result["catalog_status"], "metadata_only")
        for field in ("execution_enabled", "installed", "network_used", "model_downloaded"):
            self.assertFalse(result[field])

    def test_wrapped_archive_plugin_root_is_supported(self):
        value = self.accept([
            ("black_and_white/plugin.json", self.manifest()),
            ("black_and_white/icon.svg", b"<svg/>"),
        ])
        self.assertEqual(value["id"], MANIFEST["id"])

    def test_native_ai_model_declared_but_never_downloaded(self):
        value = self.accept([("plugin.json", self.manifest(
            plugin_type="native_ai",
            models=[{"name": "unsafe.onnx", "url": "https://example.invalid/m.onnx"}],
        ))])
        self.assertTrue(value["declares_models"])
        self.assertFalse(value["model_downloaded"])

    def test_script_is_not_evaluated(self):
        value = self.accept([
            ("plugin.json", self.manifest(plugin_type="interactive_ui")),
            ("logic.rhai", b"throw \"should never run\";"),
        ])
        self.assertEqual(value["catalog_status"], "metadata_only")
        self.assertFalse(value["execution_enabled"])

    def test_rejects_invalid_json_and_duplicate_fields(self):
        for payload in (b"{", b"[]", b"\xff", b'{"id":"a","id":"b"}',
                        b'{"id":"x","extra":{"a":1,"a":2}}',
                        self.manifest(version="NaN").replace(b'"version": "NaN"', b'"version": NaN')):
            with self.subTest(payload=payload[:35]):
                self.reject([("plugin.json", payload)])

    def test_rejects_missing_and_duplicate_manifest(self):
        self.reject([("README.md", b"not a plugin")])
        self.reject([
            ("plugin.json", self.manifest()),
            ("nested/plugin.json", self.manifest()),
        ])

    def test_rejects_mixed_roots(self):
        self.reject([
            ("one/plugin.json", self.manifest()),
            ("other/icon.svg", b"x"),
        ])

    def test_rejects_invalid_manifest_fields(self):
        changes = [
            {"id": "../evil"},
            {"id": "a"},
            {"name": ""},
            {"name": 23},
            {"version": "latest"},
            {"plugin_type": "executable_jar"},
            {"commands": "layer.erase"},
            {"models": [1] * 65},
        ]
        for update in changes:
            with self.subTest(update=update):
                self.reject([("plugin.json", self.manifest(**update))])

    def test_rejects_archive_path_tricks(self):
        for name in (
            "../plugin.json", "/plugin.json", "x/../plugin.json",
            "x/./plugin.json", "x//plugin.json", "x\\plugin.json",
            "x:C/plugin.json", "evil\n/plugin.json",
        ):
            with self.subTest(name=name):
                self.reject([
                    ("plugin.json", self.manifest()),
                    (name, b"payload"),
                ])

    def test_rejects_executables_and_model_weights(self):
        for name in (
            "shell.sh", "plugin.exe", "model.onnx", "model.pth",
            "model.gguf", "module.so", "payload.py", "blob.bin",
        ):
            with self.subTest(name=name):
                self.reject([("plugin.json", self.manifest()), (name, b"x")])

    def test_rejects_zip_member_duplicates(self):
        self.reject([
            ("plugin.json", self.manifest()),
            ("README.md", b"first"),
            ("README.md", b"second"),
        ])

    def test_rejects_special_files_and_symlinks(self):
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFIFO | 0o644, stat.S_IFDIR | 0o755):
            item = zipfile.ZipInfo("icon.svg")
            item.create_system = 3
            item.external_attr = mode << 16
            with self.subTest(mode=mode):
                self.reject([("plugin.json", self.manifest()), ("ignored", item)])

    def test_rejects_decompression_bomb(self):
        self.reject([
            ("plugin.json", self.manifest()),
            ("large.txt", b"A" * 100000),
        ])

    def test_rejects_member_size_limit(self):
        self.reject([
            ("plugin.json", self.manifest()),
            ("large.md", os.urandom(audit.MAX_MEMBER_BYTES + 1)),
        ])

    def test_rejects_entry_count_limit(self):
        files = [("plugin.json", self.manifest())] + [
            ("item%d.txt" % n, b"x") for n in range(audit.MAX_ENTRIES)
        ]
        self.reject(files)

    def test_rejects_oversized_outer_zip(self):
        self.write([("plugin.json", self.manifest())])
        with self.path.open("ab") as f:
            f.write(b"\0" * audit.MAX_ARCHIVE_BYTES)
        with self.assertRaises(audit.AuditError):
            audit.inspect_pcpl(self.path)

    def test_rejects_corrupted_zip(self):
        self.path.write_bytes(b"not a ZIP")
        with self.assertRaises(audit.AuditError):
            audit.inspect_pcpl(self.path)

    def test_rejects_symlink_source_file(self):
        original = self.accept()
        link = Path(self.tmp.name) / "link.pcpl"
        link.symlink_to(self.path)
        self.assertEqual(original["catalog_status"], "metadata_only")
        with self.assertRaises(audit.AuditError):
            audit.inspect_pcpl(link)

    def test_rejects_non_pcpl_extension(self):
        path = Path(self.tmp.name) / "sample.zip"
        path.write_bytes(packed([("plugin.json", self.manifest())]))
        with self.assertRaises(audit.AuditError):
            audit.inspect_pcpl(path)

    def test_no_side_effects_even_with_declared_remote_model(self):
        self.write([("plugin.json", self.manifest(
            plugin_type="native_ai", models=[{"url": "https://example.invalid/private"}]
        ))])
        with patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("execution")):
            result = audit.inspect_pcpl(self.path)
        self.assertFalse(result["network_used"])
        self.assertEqual(set(Path(self.tmp.name).iterdir()), {self.path})


if __name__ == "__main__":
    unittest.main(verbosity=2)
