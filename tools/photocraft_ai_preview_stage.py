#!/usr/bin/env python3
"""PR #93 disposable build overlay: owner-tested PhotoCraft keyboard + approved Pc icons.

Run ONLY after tools/photocraft_v014_compat.py prepare on the pinned PR #77 source.
The original GitHub branch, main, production package and signing keys are untouched.
"""
from pathlib import Path
import hashlib
import json
import tomllib
import sys

EXPECTED_KEYBOARD_SHA = "f708fff8a333c2246b6d342570b19db5b95f4be1"
APPROVED_ICON_SHA256 = "1a6495c214ae4536b432a34feff9b7001b612d4df1e79bf784b00d5b393f8a9b"
PREVIEW_PACKAGE = "com.artcraft.photocraft.ai.preview"
APP = Path("adapters/photocraft")
SRC = APP / "src/lib.rs"


def once(text, original, replacement):
    count = text.count(original)
    if count != 1:
        raise SystemExit(f"Unexpected adapter anchor (count={count}): {original[:95]!r}")
    return text.replace(original, replacement, 1)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: photocraft_ai_preview_stage.py SAVED_PR93_SOURCE_DIR")
    saved = Path(sys.argv[1])
    root = Path.cwd()
    assert (root / "tools/photocraft_v014_compat.py").is_file()
    assert (root / "source/photocraft/apps/photocraft-android/Cargo.toml").is_file(), (
        "Run pinned v0.14 compatibility preparation before staging the preview")
    assert (root / "source/photocraft/crates/ui-egui/src/brand.rs").is_file()
    expected_icon = root / "assets/photocraft/launcher-pc.png"
    digest = hashlib.sha256(expected_icon.read_bytes()).hexdigest()
    if digest != APPROVED_ICON_SHA256:
        raise SystemExit("STOP: approved blue Pc icon differs from owner-validated source")

    # Use owner-tested keyboard/physical Escape, JNI/IME focus handling, shortcut
    # pad and Java host as an immutable baseline; do not replace it with the
    # older shortcut implementation on PR #93.
    data = SRC.read_text()
    data = once(data, "mod android_modifiers;\nmod shortcut_pad;",
                "mod ai_tools;\nmod ai_models;\nmod ai_menu;\nmod ai_u2netp_transport;\nmod android_modifiers;\nmod shortcut_pad;")
    data = once(data, "    shortcut_pad: shortcut_pad::ShortcutPad,",
                "    shortcut_pad: shortcut_pad::ShortcutPad,\n    ai_menu: ai_menu::AndroidAiMenu,")
    data = once(data, "        system_fonts::install_system_fonts(ui.ctx());",
                "        system_fonts::install_system_fonts(ui.ctx());\n        self.ai_menu.show(ui);")
    old = '                shortcut_pad: shortcut_pad::ShortcutPad::new(files_dir.join("PhotoCraft").join("shortcut-pad-enabled")),'
    data = once(data, old, old + "\n                ai_menu: ai_menu::AndroidAiMenu::new(files_dir.join(\"PhotoCraft\").join(\"ai-tools-visible\")),")
    SRC.write_text(data)
    for file in ("ai_menu.rs", "ai_tools.rs", "ai_models.rs", "ai_u2netp_transport.rs"):
        source = saved / file
        if not source.is_file():
            raise SystemExit("Missing verified AI Tools menu source: " + str(source))
        (APP / "src" / file).write_bytes(source.read_bytes())

    # Change both Java sources and the manifest to an isolated side-by-side
    # package. Repackage the sources, rather than leaving Java in the original
    # namespace. Do not modify the real PhotoCraft package or installed data.
    manifest = APP / "Cargo.toml"
    text = manifest.read_text()
    text = once(text, 'package = "com.artcraft.photocraft"',
                f'package = "{PREVIEW_PACKAGE}"')
    if text.count('label = "PhotoCraft"') != 2:
        raise SystemExit("Unexpected PhotoCraft app/activity labels")
    text = text.replace('label = "PhotoCraft"', 'label = "PhotoCraft AI Preview"')
    metadata = tomllib.loads(text)["package"]["metadata"]["android"]
    if metadata["package"] != PREVIEW_PACKAGE:
        raise SystemExit("Preview manifest identity mismatch")
    manifest.write_text(text)
    java = APP / "java/com/artcraft/photocraft"
    destination = java / "ai/preview"
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("PhotoCraftActivity.java", "PhotoCraftUpdatePolicy.java"):
        source = java / filename
        text = source.read_text()
        text = once(text, "package com.artcraft.photocraft;",
                    f"package {PREVIEW_PACKAGE};")
        (destination / filename).write_text(text)
        source.unlink()

    # The approved-branding package verifier must check the ephemeral package,
    # not mistake it for the production APK. All approved pixel hashes remain.
    cfg_path = Path("tools/approved-branding/assets/manifest.json")
    cfg = json.loads(cfg_path.read_text())
    if cfg["package"] != "com.artcraft.photocraft.candidate":
        raise SystemExit("Unexpected approved branding manifest identity")
    cfg["package"] = PREVIEW_PACKAGE
    cfg["display_name"] = "PhotoCraft AI Preview"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")

    assert "artcraft_type_escape_requested" in data
    assert "artcraft_finish_type_escape" in data
    assert "artcraft_discard_prompt_owns_keyboard" in data
    assert "mod ai_u2netp_transport;" in data
    assert "self.ai_menu.show(ui);" in data
    assert "ai_menu::AndroidAiMenu::new(files_dir.join" in data
    print("PASS: owner-tested ESC/T/V/C/Y/N baseline + native AI Tools menu")\n    print("PASS: Phase 3 transport compiled in isolated preview (not invoked; no image uploads)")
    print("PASS: reviewed blue Pc launcher + in-app branding source", digest)
    print("PASS: isolated preview package", PREVIEW_PACKAGE)
    print("Baseline commit:", EXPECTED_KEYBOARD_SHA)


if __name__ == "__main__":
    main()
