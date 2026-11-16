#!/usr/bin/env python3
"""Read-only ComfyUI readiness check for PhotoCraft on the SAME Android tablet.

Run inside Linux Lab with: python3 linux_lab_comfy_probe.py --check
No dependency installation, model download, external network, or image upload.
ComfyUI must already be listening at 127.0.0.1:8188.
"""
from __future__ import annotations

import argparse
import http.client
import json
import sys

LOOPBACK = "127.0.0.1"
PORT = 8188
MAX_REPLY = 128 * 1024


def read_json(path: str, *, port: int = PORT) -> object:
    if path not in ("/system_stats", "/models/checkpoints"):
        raise ValueError("Only read-only ComfyUI readiness endpoints are supported")
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError("Invalid local ComfyUI port")
    conn = http.client.HTTPConnection(LOOPBACK, port=port, timeout=5)
    try:
        conn.request("GET", path, headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        })
        response = conn.getresponse()
        if response.status != 200:
            raise RuntimeError(f"ComfyUI {path} returned HTTP {response.status}")
        if response.getheader("Content-Encoding") not in (None, "identity"):
            raise RuntimeError("Unexpected ComfyUI content encoding")
        declared = response.getheader("Content-Length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_REPLY):
            raise RuntimeError("ComfyUI response length outside the safety limit")
        body = response.read(MAX_REPLY + 1)
        if len(body) > MAX_REPLY:
            raise RuntimeError("ComfyUI response exceeded the safety limit")
        return json.loads(body)
    finally:
        conn.close()


def check(*, port: int = PORT) -> dict:
    status = read_json("/system_stats", port=port)
    if not isinstance(status, dict) or not isinstance(status.get("devices"), list):
        raise RuntimeError("Endpoint does not return ComfyUI system statistics")
    models = read_json("/models/checkpoints", port=port)
    if not isinstance(models, list) or not all(isinstance(m, str) for m in models):
        raise RuntimeError("Unexpected ComfyUI checkpoint catalog")
    # The list represents filenames, not verified, ready-to-run AI pipelines.
    return {
        "status": "comfyui_reachable",
        "endpoint": f"http://{LOOPBACK}:{port}",
        "checkpoint_count": len(models),
        "checkpoint_names": sorted(models)[:20],
        "generation_ready": False,
        "warning": (
            "Read-only catalog check; no inference or app integration tested. "
            "Actual model, node, memory and license compatibility must be verified separately."
        ),
    }



# Offline-only preflight for future masked Fill jobs. Never submits a prompt.
MAX_JOB_PIXELS = 20_000_000
MAX_PROMPT_CHARS = 2000

def preflight_masked_fill(*, width: int, height: int, prompt: str,
                          mask_pixels: int, document_revision: str,
                          consent: bool) -> dict:
    """Validate job metadata without reading images or contacting ComfyUI.

    A successful result is NOT permission to upload, generate, or edit.
    The caller must independently validate the actual mask and source revision.
    """
    if not consent:
        raise ValueError("Explicit per-image consent required")
    if any(type(n) is not int for n in (width, height, mask_pixels)):
        raise ValueError("Dimensions and mask count must be integers")
    if width < 1 or height < 1 or width * height > MAX_JOB_PIXELS:
        raise ValueError("Image dimensions outside the safety limit")
    if not 0 < mask_pixels <= width * height:
        raise ValueError("A nonempty bounded selection mask is required")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError("Prompt is empty or too long")
    if not isinstance(document_revision, str) or not (1 <= len(document_revision) <= 128):
        raise ValueError("A source document revision is required")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in document_revision):
        raise ValueError("Invalid source document revision")
    return {"preflight_only": True, "generation_ready": False,
            "width": width, "height": height, "mask_pixels": mask_pixels,
            "document_revision": document_revision}

def self_test_masked_fill_preflight() -> None:
    args = dict(width=64, height=32, prompt="remove blemish",
                mask_pixels=8, document_revision="rev-1", consent=True)
    assert preflight_masked_fill(**args)["generation_ready"] is False
    for patch in ({"consent": False}, {"mask_pixels": 0},
                  {"mask_pixels": 2049}, {"width": 0},
                  {"width": 5000, "height": 5000},
                  {"prompt": ""}, {"document_revision": ""}, {"width": True}):
        try:
            preflight_masked_fill(**{**args, **patch})
        except ValueError:
            continue
        raise AssertionError(f"Accepted unsafe preflight input: {patch}")

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        self_test_masked_fill_preflight()
        print(json.dumps(check(), indent=2))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, http.client.HTTPException) as exc:
        print(json.dumps({
            "status": "not_ready",
            "endpoint": f"http://{LOOPBACK}:{PORT}",
            "error": str(exc),
            "hint": "Start local ComfyUI inside Linux Lab and keep the Linux Lab window visible."
        }, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
