#!/usr/bin/env python3
"""PhotoCraft Companion Phase 2: small, explicit Linux Lab localhost client.

Port 18492 speaks one JSON object per line. The tablet's Companion menu must
be enabled first. This script never executes arbitrary plugin code, scans
folders, uploads pixels, or exposes the control token on the command line.

Companion reference: https://github.com/kobaltgit/photocraft-companion
The supported no-code macro commands are a deliberately small subset.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import socket
import sys

MAX_REPLY = 2 * 1024 * 1024 + 1024
SAFE_PLUGIN_COMMANDS = frozenset({
    "layer.duplicate",
    "image.adjustments.desaturate",
    "layer.newAdjustmentLayer.blackWhite",
})
EDIT_COMMANDS = frozenset(SAFE_PLUGIN_COMMANDS | {"edit.undo", "edit.redo"})


class CompanionError(RuntimeError):
    pass


class CompanionClient:
    def __init__(self, token: str, port: int = 18492):
        if not (len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token)):
            raise CompanionError("Pairing token must be 64 hexadecimal characters")
        if not (1 <= port <= 65535):
            raise CompanionError("Invalid local port")
        # Strict loopback: never send the bearer token to a LAN, web host or proxy.
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.socket.settimeout(30)
        self.reader = self.socket.makefile("rb")
        self.next_id = 1
        try:
            self.call("auth", {"token": token})
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            self.reader.close()
        finally:
            self.socket.close()

    def call(self, method: str, params: dict | None = None):
        request_id = self.next_id
        self.next_id += 1
        packet = json.dumps({"id": request_id, "method": method, "params": params or {}},
                            separators=(",", ":")).encode("utf-8") + b"\n"
        if len(packet) > 64 * 1024:
            raise CompanionError("Control request exceeds the 64 KiB limit")
        self.socket.sendall(packet)
        line = self.reader.readline(MAX_REPLY + 1)
        if not line or len(line) > MAX_REPLY or not line.endswith(b"\n"):
            raise CompanionError("Missing, incomplete or oversized PhotoCraft reply")
        try:
            reply = json.loads(line)
        except (ValueError, UnicodeDecodeError) as e:
            raise CompanionError("Malformed PhotoCraft JSON reply") from e
        if not isinstance(reply, dict) or reply.get("id") != request_id:
            raise CompanionError("Mismatched PhotoCraft request/reply ID")
        if reply.get("ok") is not True:
            raise CompanionError(str(reply.get("error", "PhotoCraft command failed")))
        return reply.get("result")

    def command(self, name: str):
        if name not in EDIT_COMMANDS | {"document.inspect", "session.inspect"}:
            raise CompanionError(f"Unsupported Companion command: {name}")
        return self.call("engine.execute", {"command": name, "params": {}})


def load_no_code_plugin(path: str) -> tuple[str, list[str]]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CompanionError(f"Cannot load no-code plugin manifest: {e}") from e
    if not isinstance(manifest, dict) or manifest.get("plugin_type") != "no_code":
        raise CompanionError("Only declarative plugin_type=no_code JSON is supported")
    name = manifest.get("name")
    entries = manifest.get("commands")
    if not isinstance(name, str) or not (0 < len(name) <= 120):
        raise CompanionError("Plugin must have a short name")
    if not isinstance(entries, list) or not (1 <= len(entries) <= 6):
        raise CompanionError("Plugin must contain 1 to 6 allowed steps")
    commands = []
    for step in entries:
        if not isinstance(step, dict) or not isinstance(step.get("command"), str):
            raise CompanionError("Invalid no-code plugin step")
        command = step["command"]
        if command not in SAFE_PLUGIN_COMMANDS:
            raise CompanionError(f"Unsupported or unsafe plugin command: {command}")
        if step.get("params", {}) != {}:
            raise CompanionError("Only empty-parameter approved plugin steps are supported")
        commands.append(command)
    return name, commands


def run_plugin(client: CompanionClient, commands: list[str]):
    """Execute sequential undoable commands. Never retry a failed edit blindly."""
    executed = []
    for cmd in commands:
        try:
            client.command(cmd)
        except CompanionError as e:
            raise CompanionError(
                f"Plugin stopped after {len(executed)} completed step(s) {executed}: {e}. "
                "If changes were applied, use Undo for each completed edit."
            ) from e
        executed.append(cmd)
    return executed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PhotoCraft Android Phase 2 Companion / Linux Lab")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ping", action="store_true", help="Authenticated, read-only handshake")
    group.add_argument("--inspect", action="store_true", help="Inspect active document and session")
    group.add_argument("--dry-run", metavar="PLUGIN.JSON", help="Validate plugin without connecting")
    group.add_argument("--run", metavar="PLUGIN.JSON", help="Run approved no-code plugin commands")
    group.add_argument("--undo", action="store_true", help="Undo last PhotoCraft edit")
    group.add_argument("--redo", action="store_true", help="Redo last PhotoCraft edit")
    parser.add_argument("--confirm-edits", action="store_true",
                        help="Acknowledge on-device edits (also enable them in PhotoCraft)")
    parser.add_argument("--port", type=int, default=18492, help="Android localhost bridge port")
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            name, commands = load_no_code_plugin(args.dry_run)
            print(json.dumps({"name": name, "approvedSteps": commands, "willEdit": False}, indent=2))
            return 0
        commands = None
        if args.run:
            name, commands = load_no_code_plugin(args.run)
        if (commands or args.undo or args.redo) and not args.confirm_edits:
            raise CompanionError("Add --confirm-edits after reviewing the macro/command and enable edits in the PhotoCraft dialog")
        token = os.environ.get("PHOTOCRAFT_COMPANION_TOKEN") or getpass.getpass(
            "Paste PhotoCraft one-session control token (input hidden): ")
        with CompanionClient(token.strip(), args.port) as client:
            status = client.call("companion.ping", {})
            if args.ping:
                print(json.dumps(status, indent=2))
            elif args.inspect:
                for command in ("session.inspect", "document.inspect"):
                    try:
                        print(json.dumps({command: client.command(command)}, indent=2))
                    except CompanionError as e:
                        print(f"{command}: {e}", file=sys.stderr)
            else:
                if status.get("readOnly") is not False:
                    raise CompanionError("Paired bridge is read-only. Enable approved undoable edits on the tablet first")
                if commands is not None:
                    print(json.dumps({"plugin": name, "completed": run_plugin(client, commands)}, indent=2))
                else:
                    command = "edit.undo" if args.undo else "edit.redo"
                    print(json.dumps({"command": command, "result": client.command(command)}, indent=2))
    except (CompanionError, OSError, TimeoutError) as e:
        print(f"Companion error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
