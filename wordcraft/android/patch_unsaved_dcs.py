"""WordCraft v0.9.0 modal keys; retain its existing guarded save command."""
from pathlib import Path
import sys

def apply(root):
    target = Path(root) / "crates/ui-egui/src/dialogs.rs"
    source = target.read_text()
    start = source.index('        Dialog::SaveChanges { name, message, .. } => {')
    end = source.index('        Dialog::RecipientList', start)
    old = source[start:end]
    new = old.replace('ui.button(tl!("Cancel"))', 'ui.button(format!("{} (C)", tl!("Cancel")))').replace('ui.button(tl!("Don\'t Save"))', 'ui.button(format!("{} (D)", tl!("Don\'t Save")))').replace('primary_button(ui, tl!("Save"))', 'primary_button(ui, format!("{} (S)", tl!("Save")))')
    anchor = '            let answer = if ui.input(|i| i.key_pressed(egui::Key::Escape)) {'
    replacement = '''            let queued = ui.ctx().data_mut(|data| data.remove_temp::<u8>(egui::Id::new("wordcraft.unsaved.dcs")));
            let shortcut = match queued.or_else(|| take_dcs(ui.ctx())) {
                Some(1) => Some("dontSave"), Some(2) => Some("cancel"), Some(3) => Some("save"), _ => None,
            };
            let answer = if let Some(answer) = shortcut {
                Some(answer)
            } else if ui.input(|i| i.key_pressed(egui::Key::Escape)) {'''
    if new == old or new.count(anchor) != 1: raise ValueError("WordCraft upstream dialog anchor changed")
    new = new.replace(anchor, replacement, 1)
    source = source[:start] + new + source[end:]
    target.write_text(source + HELPER + Path(__file__).with_name("dcs_tests.rs").read_text())

HELPER = '\n/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.\nfn take_dcs(ctx: &egui::Context) -> Option<u8> {\n    ctx.input_mut(|i| {\n        let mut answer = None;\n        let mut consumed = false;\n        i.events.retain(|e| {\n            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {\n                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };\n                if action != 0 && !modifiers.any() {\n                    consumed = true;\n                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }\n                    return false;\n                }\n            }\n            true\n        });\n        if consumed {\n            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));\n        }\n        answer\n    })\n}\n\nimpl WordApp {\n    pub fn android_unsaved_dcs_active(&self) -> bool {\n        matches!(self.dialog, Some(Dialog::SaveChanges { .. }))\n    }\n\n    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {\n        if self.android_unsaved_dcs_active() {\n            if let Some(action) = take_dcs(ctx) {\n                ctx.data_mut(|d| d.insert_temp(egui::Id::new("wordcraft.unsaved.dcs"), action));\n            }\n        }\n    }\n}\n'
if __name__ == "__main__": apply(sys.argv[1])
