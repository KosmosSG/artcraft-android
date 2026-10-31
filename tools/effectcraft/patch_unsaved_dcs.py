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
         'let (label, key) = if revert { ("  Revert  ", "dialog.unsaved.revert") } else { ("   Save   ", "dialog.unsaved.save") };\n            let save_hint = format!("{} (S)", tr("Save"));\n            let label = if revert { label } else { save_hint.as_str() };'),
        ('let r = ui.button(tr("Cancel"));\n            app.auto.add("dialog.unsaved.cancel", r.rect, "Cancel");',
         'let r = ui.button(if revert { tr("Cancel").to_string() } else { format!("{} (C)", tr("Cancel")) });\n            app.auto.add("dialog.unsaved.cancel", r.rect, "Cancel");'),
        ('let r = ui.button(tr("Don\'t Save"));',
         'let r = ui.button(format!("{} (D)", tr("Don\'t Save")));'),
        ('    if answer.is_none() && ctx.input(|i| i.key_pressed(egui::Key::Escape)) {',
         '''    // Android hardware dispatch queues a dialog-only action without touching IME text.
    if answer.is_none() && !revert {
        let queued = ctx.data_mut(|d| d.remove_temp::<u8>(egui::Id::new("effectcraft.unsaved.dcs")));
        let key = queued.or_else(|| take_dcs(ctx));
        answer = match key { Some(1) => Some(Answer::Discard), Some(2) => Some(Answer::Cancel), Some(3) => Some(Answer::Save), _ => None };
    }
    if answer.is_none() && ctx.input(|i| i.key_pressed(egui::Key::Escape)) {'''),
    ]
    for before, after in substitutions:
        if source.count(before) != 1:
            raise RuntimeError("Unexpected EffectCraft upstream dialog; refusing patch: " + before[:80])
        source = source.replace(before, after, 1)
    helper = r'''
/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.
fn take_dcs(ctx: &egui::Context) -> Option<u8> {
    ctx.input_mut(|i| {
        let mut answer = None;
        let mut consumed = false;
        i.events.retain(|e| {
            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {
                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };
                if action != 0 && !modifiers.any() {
                    consumed = true;
                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }
                    return false;
                }
            }
            true
        });
        if consumed {
            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));
        }
        answer
    })
}

impl EffectcraftApp {
    pub fn android_unsaved_dcs_active(&self) -> bool {
        self.dialog == Some(Dialog::UnsavedChanges) && !is_revert(self)
            && self.dialog_state.unsaved.command.is_some()
    }

    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {
        if self.android_unsaved_dcs_active() {
            if let Some(action) = take_dcs(ctx) {
                ctx.data_mut(|d| d.insert_temp(egui::Id::new("effectcraft.unsaved.dcs"), action));
            }
        }
    }
}
'''
    source = source.replace("enum Answer {", helper + "\nenum Answer {", 1)
    source = source.replace("enum Answer {", Path(__file__).with_name("dcs_tests.rs").read_text() + "\nenum Answer {", 1)
    target.write_text(source)
    print("PASS: EffectCraft-only Unsaved Changes D/C/S labels and keys staged")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_unsaved_dcs.py <upstream-effectcraft-root>")
    apply(Path(sys.argv[1]))
