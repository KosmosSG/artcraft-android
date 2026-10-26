#!/usr/bin/env python3
"""Android Escape/focus handoff structural checks (not device or APK tests).

Opt-in, branch-isolated regression guard for each ArtCraft application. It
requires the Escape event to reach upstream and prevents unconditional capture
of printable text/Chinese IME input.
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def require(path: str, *needles: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in source:
            raise AssertionError(f"{path}: missing {needle!r}")
    return source

def main(app: str) -> None:
    if app == "photocraft":
        source = require(
            "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java",
            "boolean dispatchKeyEvent(KeyEvent event)",
            "KeyEvent.KEYCODE_ESCAPE", "&& imeWanted",
            "imeHide();", "return super.dispatchKeyEvent(event);",
            "view.clearFocus();", "artcraftRestoreCanvasFocus()",
        )
        assert source.index("imeHide();", source.index("boolean dispatchKeyEvent")) < source.index("return super.dispatchKeyEvent(event);")
    elif app == "designcraft":
        path = "tools/designcraft/support/patch_launcher.py"
        source = require(
            path, "KeyEvent.KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "artcraftRestoreCanvasFocus()",
            "android.view.SurfaceView",
        )
        ast.parse(source, filename=path)
    elif app == "filmcraft":
        path = "tools/filmcraft/runtime_patch.py"
        source = require(
            path, "KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "artcraftRestoreCanvasFocus()",
            "android.view.SurfaceView",
        )
        ast.parse(source, filename=path)
    elif app == "effectcraft":
        path = "tools/effectcraft/integrate_updater.py"
        source = require(
            path, "KeyEvent.KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "artcraftRestoreCanvasFocus()",
            'once(j,', "imeHide();",
        )
        ast.parse(source, filename=path)
    else:
        raise SystemExit(f"Unsupported app: {app}")
    if app == "photocraft":
        require("adapters/photocraft/src/lib.rs", "let was_editing_type = self.inner.ui.text_edit.is_some();",
                "was_editing_type && self.inner.ui.text_edit.is_none()", 'jni_str!("pcEndTypeEditing")')
        require("adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java",
                "public void pcEndTypeEditing()", "imeEvents.clear();")
    require({"photocraft": "adapters/photocraft/java/com/artcraft/photocraft/PhotoCraftActivity.java",
             "designcraft": "tools/designcraft/support/patch_launcher.py",
             "filmcraft": "tools/filmcraft/runtime_patch.py",
             "effectcraft": "tools/effectcraft/integrate_updater.py"}[app],
            "event.getRepeatCount() == 0", "event.hasNoModifiers()")
    source = (ROOT / 'tools/designcraft/support/patch_launcher.py').read_text()
    assert 'memory.surrender_focus(id)' not in source, 'Do not destroy the text editor Escape lock before input processing'
    assert 'escape_hide_taskbar' not in source
    print(f"PASS: {app} Escape-to-canvas focus markers; APK/device verification still needed")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python escape_focus_check.py <app>")
    main(sys.argv[1])
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "tools/keyboard/test_native_focus.py")], check=True)
