#!/usr/bin/env python3
"""Read-only model/checksum check for prospective LaMa object removal in Linux Lab."""
import hashlib
import json
from pathlib import Path
MODEL_SHA256 = "344c77bbcb158f17dd143070d1e789f38a66c04202311ae3a258ef66667a9ea9"
MODEL_SIZE = 205669692


def inspect(home: Path) -> dict:
    model = home / "ComfyUI/models/inpaint/big-lama.pt"
    nodes = home / "ComfyUI/custom_nodes/comfyui-inpaint-nodes"
    found = model.is_file() and not model.is_symlink()
    valid = False
    if found and model.stat().st_size == MODEL_SIZE:
        digest = hashlib.sha256()
        with model.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                digest.update(chunk)
        valid = digest.hexdigest() == MODEL_SHA256
    return {
        "model_file_found": found, "model_sha256_valid": valid,
        "inpaint_nodes_present": nodes.is_dir(),
        "ready_for_integration": valid and nodes.is_dir(),
        "notice": "Read-only checks; no model execution, downloads, or ComfyUI modifications.",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(Path.home()), indent=2))
