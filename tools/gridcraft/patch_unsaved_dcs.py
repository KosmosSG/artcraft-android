"""GridCraft v0.11.1 modal keys and acknowledged Android save-and-close."""
from pathlib import Path
import sys

def apply(root):
 root=Path(root);p=root/'crates/ui-egui/src/dialogs.rs';s=p.read_text()
 start=s.index('                "saveChanges" => {',s.index('pub fn show'))
 end=s.index('                "start" => {',start)
 old=s[start:end];new=old
 for label,key in [("Don't Save","D"),("Cancel","C"),("Save","S")]:
  new=new.replace('ui.button("'+label+'")','ui.button(format!("{} ('+key+')", app.ui.language.tr("'+label+'")))')
 new=new.replace('                    ui.horizontal(|ui| {','''                    let shortcut = ui.ctx().data_mut(|data| data.remove_temp::<u8>(egui::Id::new("gridcraft.unsaved.dcs"))).or_else(|| take_dcs(ui.ctx()));
                    ui.horizontal(|ui| {''')
 new=new.replace('tr("Don\'t Save"))).clicked() {','tr("Don\'t Save"))).clicked() || shortcut == Some(1) {')
 new=new.replace('tr("Cancel"))).clicked() {','tr("Cancel"))).clicked() || shortcut == Some(2) {')
 new=new.replace('if ui.button(format!("{} (S)", app.ui.language.tr("Save"))).clicked() &&','if (shortcut == Some(3) || ui.button(format!("{} (S)", app.ui.language.tr("Save"))).clicked()) &&')
 new=new.replace('                            app.run_or_alert("file.save", json!({}));','                            if app.services.android_save_close.is_some() {\n                                app.android_save_and_close(quitting);\n                            } else {\n                            app.run_or_alert("file.save", json!({}));')
 new=new.replace('                            open = false;\n                        }\n                    });', '                            }\n                            open = false;\n                        }\n                    });')
 if old==new:raise ValueError('Already patched')
 p.write_text(s[:start]+new+s[end:]+HELPER)
 p=root/'crates/ui-egui/src/lib.rs';s=p.read_text()
 def once(old,new):
  nonlocal s
  if s.count(old)!=1:raise ValueError('GridCraft anchor changed: '+old[:60])
  s=s.replace(old,new,1)
 once('pub struct Services {','pub struct Services {\n    pub android_save_close: Option<Box<dyn Fn(&str, &[u8], std::sync::mpsc::Sender<bool>)>>,')
 once('pub struct SheetApp {','pub struct SheetApp {\n    android_pending_close: Option<(u64,u64,std::sync::mpsc::Receiver<bool>,bool)>,')
 once('        SheetApp {','        SheetApp {\n            android_pending_close: None,')
 once('    pub fn logic(&mut self, ctx: &egui::Context) {','    pub fn logic(&mut self, ctx: &egui::Context) {\n        self.android_poll_save_close(ctx);')
 p.write_text(s+Path(__file__).with_name('save_close.rs').read_text()+Path(__file__).with_name('dcs_tests.rs').read_text()+Path(__file__).with_name('editor_escape.rs').read_text())

HELPER = '\n/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.\nfn take_dcs(ctx: &egui::Context) -> Option<u8> {\n    ctx.input_mut(|i| {\n        let mut answer = None;\n        let mut consumed = false;\n        i.events.retain(|e| {\n            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {\n                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };\n                if action != 0 && !modifiers.any() {\n                    consumed = true;\n                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }\n                    return false;\n                }\n            }\n            true\n        });\n        if consumed {\n            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));\n        }\n        answer\n    })\n}\n\nimpl SheetApp {\n    pub fn android_unsaved_dcs_active(&self) -> bool {\n        self.dialog.as_ref().is_some_and(|d| d.name() == "saveChanges")\n    }\n\n    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {\n        if self.android_unsaved_dcs_active() {\n            if let Some(action) = take_dcs(ctx) {\n                ctx.data_mut(|d| d.insert_temp(egui::Id::new("gridcraft.unsaved.dcs"), action));\n            }\n        }\n    }\n}\n'
if __name__=="__main__":apply(sys.argv[1])
