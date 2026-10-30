#!/usr/bin/env python3
"""Read-only PR93 production-package readiness checks.

No APK, keystore, GitHub release, model download, or modified files.
The signed PhotoCraft upgrade is a separate owner-approved operation.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
MODULES = ROOT / "adapters" / "photocraft" / "src"
META = ROOT / "adapters" / "photocraft" / "Cargo.toml"


def need(ok: bool, why: str) -> None:
    if not ok:
        raise SystemExit("STOP: " + why)


def check() -> None:
    manifest = tomllib.loads(META.read_text())
    android = manifest["package"]["metadata"]["android"]
    need(android["package"] == "com.artcraft.photocraft",
         "Production adapter must retain com.artcraft.photocraft")
    need(android["application"]["label"] == "PhotoCraft",
         "Production app label changed")
    need(all(a["label"] == "PhotoCraft" for a in android["application"]["activity"]),
         "Production activity label changed")
    need("com.artcraft.photocraft.ai.preview" not in META.read_text(),
         "Preview identity leaked into production manifest")
    java = ROOT / "adapters" / "photocraft" / "java" / "com" / "artcraft" / "photocraft"
    # PR93's repository adapter contains PhotoCraftActivity; the prepared
    # immutable owner-tested Android v0.14 baseline supplies the additional
    # PhotoCraftUpdatePolicy host. Validate any host that exists here without
    # incorrectly requiring generated/baseline-only files in this branch.
    host = java / "PhotoCraftActivity.java"
    need(host.is_file(), "Missing production Java Activity")
    for source in (host, java / "PhotoCraftUpdatePolicy.java"):
        if source.is_file():
            need(source.read_text().startswith("package com.artcraft.photocraft;"),
                 f"Production Java namespace changed: {source.name}")

    lib = (MODULES / "lib.rs").read_text()
    for name in ("ai_tools", "ai_models", "ai_menu",
                 "ai_u2netp_transport", "ai_background_job",
                 "ai_output_validation", "ai_background_editor"):
        need(f"mod {name};" in lib, f"AI editor module missing: {name}")
        need((MODULES / f"{name}.rs").is_file(), f"AI module not staged: {name}")
    need("self.ai_menu.show(ui, &mut self.inner.session)" in lib,
         "AI menu is not connected to active PhotoCraft session")
    need("self.inner.sync_views();" in lib,
         "AI layer insertion must refresh editor views")
    need("artcraft_finish_type_escape" in lib or
         (ROOT / "templates" / "android" / "ime_bridge.rs").exists(),
         "Owner-tested typing/ESC compatibility needs verification")
    menu = (MODULES / "ai_menu.rs").read_text()
    need("ui.add_enabled(false, egui::Button::new(action.label()))" in menu,
         "Unimplemented generative AI actions must stay disabled")
    for phrase in ("self.cpu_consent", "ai_background_editor::insert_undoable",
                   "job.may_insert(current)"):
        need(phrase in menu, f"Missing consent/undo/stale-document gate: {phrase}")
    editor = (MODULES / "ai_background_editor.rs").read_text()
    for phrase in ("photocraft_io::export", "photocraft_io::import",
                   "Session", 'session.edit("AI · Remove Background"',
                   "current_revision(session) != Some(expected)"):
        need(phrase in editor, f"Missing non-destructive editor contract: {phrase}")
    transport = (MODULES / "ai_u2netp_transport.rs").read_text()
    need("endpoint.ip().is_loopback()" in transport,
         "U2NetP image transport must never target a remote host")
    need("Explicit per-image consent required" in transport,
         "Missing per-image transport consent")
    server = (ROOT / "tools" / "photocraft_ai_cpu" /
              "loopback_u2netp_server.py").read_text()
    need('ThreadingHTTPServer(("127.0.0.1", args.port)' in server,
         "Linux Lab server must bind only to loopback")
    need("REQUEST_READ_TIMEOUT" in server,
         "Server must enforce bounded upload waiting time")
    # No model weights or other private binaries should be accidentally
    # committed with the AI integration. We only scan this small PR subtree.
    disallowed = sorted(str(p.relative_to(ROOT)) for p in
        (ROOT / "tools" / "photocraft_ai_cpu").rglob("*")
        if p.is_file() and p.suffix.lower() in
        {".onnx", ".pth", ".pt", ".safetensors", ".jks", ".keystore"})
    need(not disallowed, "AI weights or signing assets must not be committed: " +
         ", ".join(disallowed))
    release = (ROOT / ".github" / "workflows" /
               "build-photocraft-release.yml").read_text()
    need("inputs.publish_release" in release and
         "refs/heads/main" in release and
         "signing certificate differs" in release,
         "Existing production publishing gates must remain intact")
    print("PASS: PhotoCraft production app name and Android package unchanged")
    print("PASS: AI modules wired into production-named adapter source")
    print("PASS: explicit consent, localhost transport, revision guard and Undo")
    print("PASS: no model weights or signing assets bundled into CPU tools")
    print("PASS: existing release workflow retains manual publish + certificate gate")
    print("NOT PROVEN: a signed in-place upgrade, licensing, Android lifecycle "
          "stability, or owner approval to publish")
    print("No APK compiled or released; no keystore or app installation modified")


if __name__ == "__main__":
    check()
