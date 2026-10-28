#!/usr/bin/env python3
"""Guarded EffectCraft v0.16.0 Android-only Unsaved Changes D/C/S enhancement.

Run against a temporary upstream checkout before compiling. Do not alter Revert.
"""
from pathlib import Path
import sys

def apply(root: Path) -> None:
    target = root / "crates/ui-egui/src/panels/unsaved.rs"
    source = target.read_text()
    substitutions = [
        ('let (label, key) = if revert { ("  Revert  ", "dialog.unsaved.revert") } else { ("   Save   ", "dialog.unsaved.save") };',
         'let (label, key) = if revert { ("  Revert  ", "dialog.unsaved.revert") } else { ("Save (S)", "dialog.unsaved.save") };'),
        ('let r = ui.button(tr("Cancel"));\n            app.auto.add("dialog.unsaved.cancel", r.rect, "Cancel");',
         'let r = ui.button(if revert { tr("Cancel").to_string() } else { "Cancel (C)".to_string() });\n            app.auto.add("dialog.unsaved.cancel", r.rect, "Cancel");'),
        ('let r = ui.button(tr("Don\'t Save"));',
         'let r = ui.button("Don\'t Save (D)");'),
        ('    if answer.is_none() && ctx.input(|i| i.key_pressed(egui::Key::Escape)) {',
         '''    // Only the Unsaved Changes dialog (not Revert) handles D/C/S.
    // Consume physical, unmodified key presses so they cannot also become tool
    // shortcuts or document text. Existing Enter/Escape remain available.
    if answer.is_none() && !revert {
        let pressed = |key| ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, key));
        if pressed(egui::Key::C) {
            answer = Some(Answer::Cancel);
        } else if pressed(egui::Key::D) {
            answer = Some(Answer::Discard);
        } else if pressed(egui::Key::S) {
            answer = Some(Answer::Save);
        }
    }
    if answer.is_none() && ctx.input(|i| i.key_pressed(egui::Key::Escape)) {'''),
    ]
    for before, after in substitutions:
        if source.count(before) != 1:
            raise RuntimeError("Unexpected EffectCraft upstream dialog; refusing patch: " + before[:80])
        source = source.replace(before, after, 1)
    target.write_text(source)
    print("PASS: EffectCraft-only Unsaved Changes D/C/S labels and keys staged")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_unsaved_dcs.py <upstream-effectcraft-root>")
    apply(Path(sys.argv[1]))
