#!/usr/bin/env python3
"""Offline tests for the actual U2NetP file bridge (no model download or inference)."""
from __future__ import annotations
import importlib.util
import io
import subprocess
from pathlib import Path
import tempfile
import unittest
import zlib
from unittest.mock import patch
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("local_background_bridge", HERE / "local_background_bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class SidecarTests(unittest.TestCase):
    def make_png(self, path):
        Image.new("RGBA", (16, 16), (50, 80, 120, 255)).save(path)

    def test_consent_required_before_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            with self.assertRaisesRegex(ValueError, "consent"):
                bridge.run(source, output, False)
            self.assertFalse(output.exists())

    def test_valid_png_passes_pillow_verification_and_reaches_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            with patch.object(bridge.subprocess, "run", side_effect=RuntimeError("MOCK_REACHED")) as runner:
                with self.assertRaisesRegex(RuntimeError, "MOCK_REACHED"):
                    bridge.run(source, output, True)
            runner.assert_called_once()
            kwargs = runner.call_args.kwargs
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertNotIn("capture_output", kwargs)
            self.assertFalse(output.exists())

    def test_rejects_non_png_before_subprocess(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.jpg", Path(folder) / "output.png"
            Image.new("RGB", (16, 16)).save(source)
            with patch.object(bridge.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "Only PNG"):
                    bridge.run(source, output, True)
                runner.assert_not_called()

    def test_oversized_png_ihdr_is_controlled_validation_error(self):
        # A CRC-correct 400 MP IHDR triggers Pillow's early bomb check,
        # even though the compressed file is tiny. No CPU inference.
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            data = source.read_bytes()
            marker = data.index(b"IHDR")
            dimensions = marker + 4
            data = data[:dimensions] + (20_000).to_bytes(4, "big") * 2 + data[dimensions + 8:]
            crc_at = marker + 4 + 13
            source.write_bytes(data[:crc_at] + zlib.crc32(data[marker:crc_at]).to_bytes(4, "big") + data[crc_at + 4:])
            with patch.object(bridge.subprocess, "run") as inference:
                with self.assertRaisesRegex(ValueError, "dimensions outside safety limit"):
                    bridge.run(source, output, True)
                inference.assert_not_called()
            self.assertFalse(output.exists())

    def test_crc_valid_but_undecodable_png_never_starts_inference(self):
        # The old image.verify() guard accepted CRC-correct PNGs whose
        # compressed IDAT stream fails only during actual pixel decoding.
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            data = source.read_bytes()
            chunk = data.index(b"IDAT") - 4
            length = int.from_bytes(data[chunk:chunk + 4], "big")
            start, end = chunk + 8, chunk + 8 + length
            self.assertGreaterEqual(length, 3)
            invalid_zlib = b"\x78\x9c" + b"\xff" * (length - 2)
            checksum = zlib.crc32(b"IDAT" + invalid_zlib).to_bytes(4, "big")
            source.write_bytes(data[:start] + invalid_zlib + checksum + data[end + 4:])
            with Image.open(io.BytesIO(source.read_bytes())) as image:
                image.verify()  # CRC passes despite invalid deflate stream.
            with patch.object(bridge.subprocess, "run") as runner:
                with self.assertRaises((OSError, ValueError)):
                    bridge.run(source, output, True)
                runner.assert_not_called()
            self.assertFalse(output.exists())

    def test_success_commits_only_validated_png_and_removes_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)

            def inference(argv, **kwargs):
                staged = Path(argv[argv.index("--output") + 1])
                self.assertNotEqual(staged, output)
                self.assertFalse(output.exists())
                self.make_png(staged)
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with patch("sys.stdout", new_callable=io.StringIO):
                    bridge.run(source, output, True)
            with Image.open(output) as image:
                image.load()
                self.assertEqual(image.size, (16, 16))
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_worker_uses_validated_input_snapshot_not_mutable_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)
            expected = source.read_bytes()

            def inference(argv, **kwargs):
                private_input = Path(argv[argv.index("--input") + 1])
                self.assertNotEqual(private_input, source)
                self.assertEqual(private_input.read_bytes(), expected)
                source.write_bytes(b"modified during inference startup")
                self.assertEqual(private_input.read_bytes(), expected)
                self.make_png(Path(argv[argv.index("--output") + 1]))
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with patch("sys.stdout", new_callable=io.StringIO):
                    bridge.run(source, output, True)
            self.assertTrue(output.is_file())
            self.assertEqual(source.read_bytes(), b"modified during inference startup")
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_failed_inference_does_not_leave_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)

            def inference(argv, **kwargs):
                Path(argv[argv.index("--output") + 1]).write_bytes(b"partial")
                return subprocess.CompletedProcess(argv, 1)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with self.assertRaisesRegex(RuntimeError, "no output committed"):
                    bridge.run(source, output, True)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_timeout_cleans_staged_output_without_touching_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)

            def inference(argv, **kwargs):
                Path(argv[argv.index("--output") + 1]).write_bytes(b"partial")
                raise subprocess.TimeoutExpired(cmd=argv, timeout=180)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with self.assertRaises(subprocess.TimeoutExpired):
                    bridge.run(source, output, True)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_child_symlink_output_never_exposes_unrelated_local_png(self):
        # A successful child could write a symlink instead of a PNG.
        # inspect() follows links, so validation alone is insufficient.
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    source, output = root / "input.png", root / "output.png"
                    unrelated = root / "unrelated.png"
                    self.make_png(source)
                    if not dangling:
                        self.make_png(unrelated)
                        original = unrelated.read_bytes()

                    def inference(argv, **kwargs):
                        staged = Path(argv[argv.index("--output") + 1])
                        staged.symlink_to(unrelated)
                        return subprocess.CompletedProcess(argv, 0)

                    with patch.object(bridge.subprocess, "run", side_effect=inference) as worker:
                        with self.assertRaisesRegex(RuntimeError, "regular PNG"):
                            bridge.run(source, output, True)
                    worker.assert_called_once()
                    self.assertFalse(output.exists())
                    self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])
                    if dangling:
                        self.assertFalse(unrelated.exists())
                    else:
                        self.assertEqual(unrelated.read_bytes(), original)

    def test_worker_stage_swap_before_publication_cannot_change_validated_png(self):
        # A surviving worker child may replace its result between validation
        # and publication. The old os.link(staged_output, destination) would
        # publish the swapped bytes. Only a trusted snapshot may be linked.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)
            observed = {}

            def inference(argv, **kwargs):
                staged = Path(argv[argv.index("--output") + 1])
                Image.new("RGBA", (16, 16), (10, 80, 130, 200)).save(staged)
                observed["staged"] = staged
                observed["expected"] = staged.read_bytes()
                return subprocess.CompletedProcess(argv, 0)

            real_link = bridge.os.link

            def swap_at_link(src, dst, **kwargs):
                staged = observed["staged"]
                self.assertNotEqual(Path(src), staged)
                staged.unlink()
                Image.new("RGBA", (16, 16), (220, 20, 20, 255)).save(staged)
                self.assertNotEqual(staged.read_bytes(), observed["expected"])
                return real_link(src, dst, **kwargs)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with patch.object(bridge.os, "link", side_effect=swap_at_link):
                    with patch("sys.stdout", new_callable=io.StringIO):
                        bridge.run(source, output, True)
            self.assertEqual(output.read_bytes(), observed["expected"])
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])
            self.assertEqual(list(root.glob("photocraft-ai-verified-*")), [])

    def test_worker_hardlink_to_unrelated_png_is_rejected(self):
        # A hardlink is a regular file, but is not an independent worker output.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            unrelated = root / "unrelated.png"
            self.make_png(source)
            self.make_png(unrelated)
            original = unrelated.read_bytes()

            def inference(argv, **kwargs):
                staged = Path(argv[argv.index("--output") + 1])
                bridge.os.link(unrelated, staged)
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with self.assertRaisesRegex(RuntimeError, "bounded regular PNG"):
                    bridge.run(source, output, True)
            self.assertFalse(output.exists())
            self.assertEqual(unrelated.read_bytes(), original)
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_racing_destination_creation_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "input.png", root / "output.png"
            self.make_png(source)

            def inference(argv, **kwargs):
                self.make_png(Path(argv[argv.index("--output") + 1]))
                output.write_bytes(b"other-writer-data")
                return subprocess.CompletedProcess(argv, 0)

            with patch.object(bridge.subprocess, "run", side_effect=inference):
                with self.assertRaisesRegex(ValueError, "new PNG"):
                    bridge.run(source, output, True)
            self.assertEqual(output.read_bytes(), b"other-writer-data")
            self.assertEqual(list(root.glob("photocraft-ai-stage-*")), [])

    def test_refuses_dangling_output_symlink_before_inference(self):
        # resolve() follows dangling symlinks, so an absent target previously
        # passed exists() and could be created outside the requested output.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "input.png"
            output = root / "output.png"
            outside = root / "different-location.png"
            self.make_png(source)
            output.symlink_to(outside)
            self.assertFalse(outside.exists())
            with patch.object(bridge.subprocess, "run") as inference:
                with self.assertRaisesRegex(ValueError, "symlink"):
                    bridge.run(source, output, True)
                inference.assert_not_called()
            self.assertTrue(output.is_symlink())
            self.assertFalse(outside.exists())

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "input.png", Path(folder) / "output.png"
            self.make_png(source)
            output.write_bytes(b"existing")
            with self.assertRaisesRegex(ValueError, "new PNG"):
                bridge.run(source, output, True)
            self.assertEqual(output.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
