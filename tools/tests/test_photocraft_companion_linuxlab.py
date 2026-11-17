"""Offline Linux Lab client contract tests (mock Android RPC; NOT a device test)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "photocraft_companion_linuxlab.py"
spec = importlib.util.spec_from_file_location("companion_client_under_test", SCRIPT)
companion = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = companion
spec.loader.exec_module(companion)
PLUGIN = ROOT / "tools" / "photocraft_companion_plugins" / "black_white.json"
TOKEN = "a" * 64


class FakeAndroidBridge:
    """Faithful wire-format mock; no PhotoCraft engine and no actual edits."""
    def __init__(self, *, write=False):
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.listener.listen(1)
        self.write = write
        self.seen = []
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            connection, _ = self.listener.accept()
            with connection:
                stream = connection.makefile("rb")
                auth = False
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    request = json.loads(line)
                    method = request["method"]
                    params = request.get("params", {})
                    self.seen.append((method, params))
                    reply = {"id": request["id"], "ok": True, "result": None}
                    if not auth:
                        if method != "auth" or params.get("token") != TOKEN:
                            reply.update(ok=False, error="authentication required")
                        else:
                            auth = True
                            reply["result"] = {"authenticated": True}
                    elif method == "companion.ping":
                        reply["result"] = {"protocol": 2, "readOnly": not self.write}
                    elif method == "engine.execute":
                        command = params.get("command")
                        read_only = command in {"session.inspect", "document.inspect"}
                        approved = command in companion.EDIT_COMMANDS and self.write
                        if read_only:
                            reply["result"] = {"mock": True, "command": command}
                        elif approved and params.get("params") == {}:
                            reply["result"] = {"edited": command}
                        else:
                            reply.update(ok=False, error="Command is not approved")
                    else:
                        reply.update(ok=False, error="Unsupported method")
                    connection.sendall(json.dumps(reply).encode() + b"\n")
                    if not auth:
                        break
                stream.close()
        finally:
            self.listener.close()

    def close(self):
        self.thread.join(timeout=3)
        assert not self.thread.is_alive(), "mock connection did not terminate"


class Phase2ClientTests(unittest.TestCase):
    def test_plugin_manifest_exact_companion_steps(self):
        name, commands = companion.load_no_code_plugin(str(PLUGIN))
        self.assertIn("Film Pop", name)
        self.assertEqual(commands, ["layer.duplicate", "image.adjustments.desaturate"])

    def test_dry_run_never_uses_network(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = companion.main(["--dry-run", str(PLUGIN)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["willEdit"], False)

    def test_rejects_unsafe_plugin_commands_and_nonempty_parameters(self):
        with self.assertRaises(companion.CompanionError):
            companion.load_no_code_plugin("/definitely/absent/plugin.json")
        import tempfile
        for cmd, params in [("app.save", {}), ("layer.duplicate", {"layer": 7})]:
            with tempfile.TemporaryDirectory() as temp:
                manifest = Path(temp) / "plugin.json"
                manifest.write_text(json.dumps({
                    "name": "unsafe", "plugin_type": "no_code",
                    "commands": [{"command": cmd, "params": params}]
                }))
                with self.assertRaises(companion.CompanionError):
                    companion.load_no_code_plugin(str(manifest))

    def test_authenticated_read_only_ping_and_document_inspection(self):
        fake = FakeAndroidBridge()
        with companion.CompanionClient(TOKEN, fake.port) as c:
            self.assertTrue(c.call("companion.ping", {})["readOnly"])
            self.assertEqual(c.command("document.inspect")["command"], "document.inspect")
            self.assertEqual(c.command("session.inspect")["command"], "session.inspect")
            with self.assertRaises(companion.CompanionError):
                c.command("layer.duplicate")
        fake.close()
        self.assertEqual([x[0] for x in fake.seen[:2]], ["auth", "companion.ping"])

    def test_wrong_authentication_rejected_before_command(self):
        fake = FakeAndroidBridge()
        with self.assertRaises(companion.CompanionError):
            companion.CompanionClient("b" * 64, fake.port)
        fake.close()
        self.assertEqual(len(fake.seen), 1)

    def test_approved_macro_runs_two_undoable_calls_in_order(self):
        fake = FakeAndroidBridge(write=True)
        _, commands = companion.load_no_code_plugin(str(PLUGIN))
        with companion.CompanionClient(TOKEN, fake.port) as c:
            self.assertEqual(companion.run_plugin(c, commands), commands)
            c.command("edit.undo")
            c.command("edit.undo")
            c.command("edit.redo")
        fake.close()
        self.assertEqual(
            [p["command"] for method, p in fake.seen if method == "engine.execute"],
            commands + ["edit.undo", "edit.undo", "edit.redo"],
        )

    def test_reject_unknown_client_commands_before_transmit(self):
        fake = FakeAndroidBridge()
        with companion.CompanionClient(TOKEN, fake.port) as c:
            with self.assertRaises(companion.CompanionError):
                c.command("app.save")
        fake.close()
        self.assertEqual(len(fake.seen), 1)


if __name__ == "__main__":
    unittest.main()
