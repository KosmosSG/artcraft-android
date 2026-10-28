"""Pinned FilmCraft v0.10.0 close/quit dialog patch; preserve its save guards."""
from pathlib import Path
import sys

def apply(root):
    target = Path(root) / 'crates/ui-egui/src/panels/clip_dialogs.rs'
    source = target.read_text()
    def once(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError('FilmCraft upstream anchor changed: ' + before[:70])
        source = source.replace(before, after, 1)
    start = source.index('            "file.closeProject" | "app.quit" => {', source.index('pub fn show('))
    end = source.index('            _ => {}', start)
    buttons = source[start:end]
    updated = buttons.replace('ui.button(tl!("Cancel"))', 'ui.button(format!("{} (C)", tl!("Cancel")))').replace('ui.button(tl!("Don\'t Save"))', 'ui.button(format!("{} (D)", tl!("Don\'t Save")))').replace('egui::Button::new(tl!("Save"))', 'egui::Button::new(format!("{} (S)", tl!("Save")))')
    if updated == buttons: raise ValueError('Already patched')
    once(buttons, updated)
    once('    if crate::widgets::escape_closes(ctx) {', '''    if action.is_none() && matches!(d.command.as_str(), "file.closeProject" | "app.quit") {
        let queued = ctx.data_mut(|data| data.remove_temp::<u8>(egui::Id::new("filmcraft.unsaved.dcs")));
        action = match queued.or_else(|| take_dcs(ctx)) {
            Some(1) => Some("dontSave"), Some(2) => Some("cancel"),
            Some(3) if can_save => Some("save"), _ => None,
        };
    }
    if crate::widgets::escape_closes(ctx) {''')
    source += HELPER + Path(__file__).with_name("dcs_tests.rs").read_text()
    target.write_text(source)

HELPER = '\n/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.\nfn take_dcs(ctx: &egui::Context) -> Option<u8> {\n    ctx.input_mut(|i| {\n        let mut answer = None;\n        let mut consumed = false;\n        i.events.retain(|e| {\n            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {\n                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };\n                if action != 0 && !modifiers.any() {\n                    consumed = true;\n                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }\n                    return false;\n                }\n            }\n            true\n        });\n        if consumed {\n            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));\n        }\n        answer\n    })\n}\n\nimpl FilmcraftApp {\n    pub fn android_unsaved_dcs_active(&self) -> bool {\n        self.ui.clip_dialog.as_ref().is_some_and(|d| matches!(d.command.as_str(), "file.closeProject" | "app.quit"))\n    }\n\n    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {\n        if self.android_unsaved_dcs_active() {\n            if let Some(action) = take_dcs(ctx) {\n                ctx.data_mut(|d| d.insert_temp(egui::Id::new("filmcraft.unsaved.dcs"), action));\n            }\n        }\n    }\n}\n'
if __name__ == '__main__': apply(sys.argv[1])
