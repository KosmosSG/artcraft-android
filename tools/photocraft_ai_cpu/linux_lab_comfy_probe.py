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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
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
