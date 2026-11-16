"""Offline LaMa readiness tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import lama_readiness as lama


class Tests(unittest.TestCase):
    def test_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(lama.inspect(Path(d))["ready_for_integration"])

    def test_invalid_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            model = home/"ComfyUI/models/inpaint/big-lama.pt"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"no")
            nodes = home/"ComfyUI/custom_nodes/comfyui-inpaint-nodes"
            nodes.mkdir(parents=True)
            with patch.object(lama, "MODEL_SIZE", 2):
                self.assertFalse(lama.inspect(home)["model_sha256_valid"])


if __name__ == "__main__":
    unittest.main()
