#!/usr/bin/env python3
"""Android-only fallback for hardware tool shortcuts without an egui Text event.

Applies solely to a throwaway checkout of pinned official VectorCraft v0.14.
Never patch installed Android apps, checked-in production sources or user keymaps.
If upstream's reviewed shortcut anchor changes, refuse to patch.
"""
from pathlib import Path
import argparse

ANCHOR = "    for (text, m) in events {\n"
INJECTION = '''    // Android's physical keyboards can send Key events without a following Text event.
    // The normal typed-text path remains authoritative whenever it exists. This fallback
    // runs only AFTER the handler's dialog, focused-field, type-editing and IME gates.
    #[cfg(target_os = "android")]
    let events = if events.is_empty() {
        ctx.input(|i| {
            // Never synthesize tool actions from active IME composition or text input.
            if i.events.iter().any(|e| matches!(e, egui::Event::Text(_) | egui::Event::Ime(_))) {
                return Vec::new();
            }
            i.events.iter().filter_map(|e| match e {
                egui::Event::Key {
                    key, physical_key, pressed: true, repeat: false, modifiers, ..
                } if !(modifiers.command || modifiers.ctrl || modifiers.alt) => {
                    // A letter only; preserve command/tool overrides and the Shift prefix
                    // by routing through the SAME editor lookups used for typed text.
                    letter_of(physical_key.unwrap_or(*key))
                        .map(|letter| (letter.to_string(), *modifiers))
                }
                _ => None,
            }).collect()
        })
    } else {
        events
    };
'''


def patch(root: Path) -> None:
    file = root / "crates/ui-egui/src/shortcuts.rs"
    before = file.read_text(encoding="utf-8")
    if before.count(ANCHOR) != 1:
        raise ValueError("upstream tool-shortcut loop changed, review required")
    if "fn letter_of(k: Key) -> Option<char>" not in before:
        raise ValueError("upstream physical key mapping changed")
    for required in (
        "let typing = ctx.egui_wants_keyboard_input();",
        "if typing {",
        "if app.session.tool_wants_text() {",
        "if composing || app.session.tool_composing() {",
        "crate::shortcut_editor::tool_for_key",
        "crate::shortcut_editor::command_for_key",
    ):
        if required not in before:
            raise ValueError(f"upstream keyboard safety guard missing: {required}")
    if "#[cfg(target_os = \"android\")]\n    let events = if events.is_empty()" in before:
        raise ValueError("already patched; refuse double injection")
    file.write_text(before.replace(ANCHOR, INJECTION + ANCHOR, 1), encoding="utf-8")
    print("PASS: Android key-only tool shortcut fallback added to pinned temporary source")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_root", type=Path)
    args = parser.parse_args()
    try:
        patch(args.upstream_root)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"STOP: Android keyboard fallback requires review: {exc}")
