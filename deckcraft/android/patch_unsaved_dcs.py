"""Pinned DeckCraft modal shortcuts and acknowledged Android save-and-close."""
from pathlib import Path
import sys

def apply(root):
    root=Path(root)
    p=root/'crates/ui-egui/src/dialogs.rs';s=p.read_text()
    start=s.index('        "quit" => {', s.index('pub fn show'))
    end=s.index('        "zoom" =>',start)
    old=s[start:end];new=old
    for label,key in [("Don't Save","D"),("Cancel","C"),("Save","S")]:new=new.replace('new("'+label+'")','new("'+label+' ('+key+')")')
    new=new.replace('            let mut done = false;','''            let shortcut = ui.ctx().data_mut(|data| data.remove_temp::<u8>(egui::Id::new("deckcraft.unsaved.dcs"))).or_else(|| take_dcs(ui.ctx()));
            let mut done = false;''')
    new=new.replace('24.0))).clicked() {\n                    let _ = app.session.execute', '24.0))).clicked() || shortcut == Some(1) {\n                    let _ = app.session.execute')
    new=new.replace('24.0))).clicked() {\n                    run(app, "file.close"', '24.0))).clicked() || shortcut == Some(1) {\n                    run(app, "file.close"')
    new=new.replace('if save.clicked() ||', 'if shortcut == Some(3) || save.clicked() ||')
    new=new.replace('24.0))).clicked() {\n                        done = true;', '24.0))).clicked() || shortcut == Some(2) {\n                        done = true;')
    new=new.replace('                        if app.save_all() {', '                        if app.services.android_save_close.is_some() {\n                            app.android_save_and_close(true);\n                        } else if app.save_all() {')
    new=new.replace('                        app.save();', '                        if app.services.android_save_close.is_some() {\n                            app.android_save_and_close(false);\n                        } else {\n                        app.save();')
    new=new.replace('                        done = true;\n                    }\n                    if ui.add', '                        done = true;\n                    }\n                    if ui.add',1)
    # Close branch gets one extra scope; preserve desktop/browser semantics inside it.
    anchor='                            run(app, "file.close", json!({}));\n                        }\n                        done = true;'
    if new.count(anchor)!=1:raise ValueError('DeckCraft close save guard changed')
    new=new.replace(anchor,anchor.replace('                        done = true;', '                        }\n                        done = true;'))
    if old==new:raise ValueError('Already patched')
    p.write_text(s[:start]+new+s[end:]+HELPER+Path(__file__).with_name('dcs_tests.rs').read_text())
    p=root/'crates/ui-egui/src/lib.rs';s=p.read_text()
    def once(a,b):
        nonlocal s
        if s.count(a)!=1:raise ValueError('DeckCraft anchor changed: '+a[:60])
        s=s.replace(a,b,1)
    once('pub enum InboxEvent {','pub enum InboxEvent {\n    AndroidSaveFinished { id: u64, success: bool },')
    once('    pub download: Option<DownloadFn>,', '    pub download: Option<DownloadFn>,\n    pub android_save_close: Option<Box<dyn FnMut(u64, &str, &[u8])>>,')
    once('pub struct SlideApp {','pub struct SlideApp {\n    android_pending_close: Option<(u64, u64, std::sync::Arc<deckcraft_model::Presentation>, bool)>,')
    once('        let audio_out = services.audio_out.take();','        let audio_out = services.audio_out.take();')
    # Unique initializer anchor found from the same constructor.
    start=s.index('    pub fn new(session: Session, mut services: Services)')
    pos=s.index('        SlideApp {',start)
    s=s[:pos]+s[pos:].replace('        SlideApp {','        SlideApp {\n            android_pending_close: None,',1)
    once('                InboxEvent::Cancelled { id } =>', '                InboxEvent::AndroidSaveFinished { id, success } => self.android_save_finished(id, success),\n                InboxEvent::Cancelled { id } =>')
    s += Path(__file__).with_name('save_close.rs').read_text()
    p.write_text(s)

HELPER = '\n/// Consume only unmodified D/C/S presses; ignore repeats and preserve IME events.\nfn take_dcs(ctx: &egui::Context) -> Option<u8> {\n    ctx.input_mut(|i| {\n        let mut answer = None;\n        let mut consumed = false;\n        i.events.retain(|e| {\n            if let egui::Event::Key { key, pressed, repeat, modifiers, .. } = e {\n                let action = match key { egui::Key::D => 1, egui::Key::C => 2, egui::Key::S => 3, _ => 0 };\n                if action != 0 && !modifiers.any() {\n                    consumed = true;\n                    if *pressed && !*repeat && answer.is_none() { answer = Some(action); }\n                    return false;\n                }\n            }\n            true\n        });\n        if consumed {\n            i.events.retain(|e| !matches!(e, egui::Event::Text(t) if matches!(t.as_str(), "d" | "D" | "c" | "C" | "s" | "S")));\n        }\n        answer\n    })\n}\n\nimpl SlideApp {\n    pub fn android_unsaved_dcs_active(&self) -> bool {\n        self.dialog.as_ref().is_some_and(|d| matches!(d.id.as_str(), "close" | "quit"))\n    }\n\n    pub fn android_capture_unsaved_dcs(&self, ctx: &egui::Context) {\n        if self.android_unsaved_dcs_active() {\n            if let Some(action) = take_dcs(ctx) {\n                ctx.data_mut(|d| d.insert_temp(egui::Id::new("deckcraft.unsaved.dcs"), action));\n            }\n        }\n    }\n}\n'
if __name__=="__main__":apply(sys.argv[1])
