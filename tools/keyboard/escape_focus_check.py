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
            "relayTypeEscape(event)", "return super.dispatchKeyEvent(event);",
            "view.clearFocus();", "child.requestFocus()",
        )
        relay = source[source.index("private boolean relayTypeEscape"):source.index("/** Called only after")]
        assert 'imeEvents.offer("e")' in relay and 'imeEvents.offer("E")' in relay
        assert "imeHide();" not in relay
        assert "onKeyPreIme(int keyCode, KeyEvent event)" in source
        for signature in ("sendKeyEvent(KeyEvent event)",
                          "onKeyDown(int keyCode, KeyEvent event)",
                          "onKeyUp(int keyCode, KeyEvent event)"):
            body = source[source.index(signature):].split("}", 1)[0]
            assert "relayTypeEscape(event)" in body, signature
        shell = (ROOT / "adapters/photocraft/src/lib.rs").read_text()
        logic = shell[shell.index("let was_editing_type"):shell.index("    fn ui(")]
        assert logic.index("self.inner.logic(ctx, frame)") < logic.index("artcraft_finish_type_escape")
        assert "std::mem::take(&mut self.type_escape_requested)" in logic
        port = (ROOT / "tools/photocraft_v014_menu_port.py").read_text()
        guard = port[port.index("pub fn artcraft_type_escape_requested"):port.index("const CUSTOM_FONTS_ID")]
        assert "edit.preedit.is_some()" not in guard
        assert "egui::Event::Ime(_)" not in guard
        for owner in ("ctx.text_edit_focused()", "app.ui.dialogs", "app.discard",
                      "crate::type_transform::active", "crate::menu_nav::is_open",
                      "crate::widgets::dropdown_list_open"):
            assert owner in guard
        require("templates/android/ime_bridge.rs", "'e' | 'E' if payload.is_empty()", "pressed: tag == 'e'")
        require("adapters/photocraft/src/lib.rs",
                "artcraft_finish_type_escape(&mut self.inner)", "self.bridge.end_type_editing()",
                "memory.surrender_focus(id)", "self.inner.raw_input_hook(ctx, raw);")
    elif app == "designcraft":
        path = "tools/designcraft/support/patch_launcher.py"
        source = require(
            path, "KeyEvent.KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "child.requestFocus()",
            "ctx.text_edit_focused()", "memory.surrender_focus(id)",
        )
        ast.parse(source, filename=path)
    elif app == "filmcraft":
        path = "tools/filmcraft/runtime_patch.py"
        source = require(
            path, "KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "child.requestFocus()",
            "ctx.text_edit_focused()", "memory.surrender_focus(id)",
        )
        ast.parse(source, filename=path)
    elif app == "effectcraft":
        path = "tools/effectcraft/integrate_updater.py"
        source = require(
            path, "KeyEvent.KEYCODE_ESCAPE", "&& imeWanted",
            "return super.dispatchKeyEvent(event);", "child.requestFocus()",
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
    print(f"PASS: {app} Escape-to-canvas focus markers; APK/device verification still needed")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python escape_focus_check.py <app>")
    main(sys.argv[1])
