"""Pinned DesignCraft v0.12.0 modal keys and acknowledged SAF close."""
from pathlib import Path
import sys

def apply(root):
 root=Path(root);p=root/'crates/ui-egui/src/dialogs.rs';s=p.read_text()
 def once(old,new):
  nonlocal s
  if s.count(old)!=1:raise ValueError('DesignCraft anchor changed '+old[:70])
  s=s.replace(old,new,1)
 once('"closeDocument" => crate::i18n::tr(&app.ui.language, "  Save  ").to_string(),','"closeDocument" => format!("{} (S)",crate::i18n::tr(&app.ui.language, "  Save  ").trim()),')
 once('crate::i18n::tr(&app.ui.language, cancel_label))).clicked();','if d.id == "closeDocument" { format!("{} (C)",crate::i18n::tr(&app.ui.language,cancel_label)) } else { crate::i18n::tr(&app.ui.language,cancel_label).to_string() })).clicked();')
 once('crate::i18n::tr(&app.ui.language, "Don\'t Save"))).clicked()', 'format!("{} (D)",crate::i18n::tr(&app.ui.language, "Don\'t Save")))).clicked()')
 once('    // Preferences › General › Interface Language takes effect at once, like any other app setting.','''    if d.id == "closeDocument" && result.is_none() {
        let action=ctx.data_mut(|data|data.remove_temp::<u8>(egui::Id::new("designcraft.unsaved.dcs"))).or_else(||take_dcs(ctx));
        match action {
            Some(1) => {d.fields.insert("discard".into(),json!(true));result=Some(true);},
            Some(2) => result=Some(false), Some(3) => result=Some(true), _=>{},
        }
    }
    // Preferences › General › Interface Language takes effect at once, like any other app setting.''')
 once('            if d.b("quitting") {\n                return app.confirm_quit_document','''            if !d.b("discard") && app.services.android_save_close.is_some() {
                return app.android_save_and_close(uid.ok_or("Missing document")?, d.b("quitting"));
            }
            if d.b("quitting") {
                return app.confirm_quit_document''')
 p.write_text(s+HELPER)
 p=root/'crates/ui-egui/src/lib.rs';s=p.read_text()
 once('pub struct Services {','pub struct Services {\n    pub android_save_close: Option<Box<dyn FnMut(&str,&[u8],std::sync::mpsc::Sender<bool>)>>,')
 once('pub struct DesignApp {','pub struct DesignApp {\n    android_pending_close: Option<(u64,u64,std::sync::mpsc::Receiver<bool>,bool)>,')
 once('        DesignApp {','        DesignApp {\n            android_pending_close: None,')
 once('    pub fn logic(&mut self, ctx: &egui::Context) {','    pub fn logic(&mut self, ctx: &egui::Context) {\n        self.android_poll_save_close(ctx);')
 once('            if !asking {','            if !asking && self.android_pending_close.is_none() {')
 p.write_text(s+Path(__file__).with_name('save_close.rs').read_text()+Path(__file__).with_name('dcs_tests.rs').read_text())

HELPER = '\n/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.\nfn take_dcs(ctx: &egui::Context) -> Option<u8> {\n    ctx.input_mut(|i| {\n        let mut answer = None;\n        let mut consumed = false;\n        i.events.retain(|e| {\n            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {\n                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };\n                if action != 0 && !modifiers.any() {\n                    consumed = true;\n                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }\n                    return false;\n                }\n            }\n            true\n        });\n        if consumed {\n            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));\n        }\n        answer\n    })\n}\n\nimpl DesignApp {\n    pub fn android_unsaved_dcs_active(&self) -> bool {\n        self.ui.dialog.as_ref().is_some_and(|d| d.id == "closeDocument")\n    }\n\n    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {\n        if self.android_unsaved_dcs_active() {\n            if let Some(action) = take_dcs(ctx) {\n                ctx.data_mut(|d| d.insert_temp(egui::Id::new("designcraft.unsaved.dcs"), action));\n            }\n        }\n    }\n}\n'
if __name__=="__main__":apply(sys.argv[1])
