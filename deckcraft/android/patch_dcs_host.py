"""Apply DeckCraft-only modal transport and SAF save acknowledgement to staging."""
from pathlib import Path
import sys,shutil
from patch_unsaved_dcs import apply
from font_paths import patch_android_font_paths
root=Path(sys.argv[1]);here=Path(__file__).parent
apply(root/'source/deckcraft')
p=root/'templates/android/system_fonts.rs';s=p.read_text()
# Preserve DeckCraft's original private import root while aligning scanner paths.
s=patch_android_font_paths(s).replace('std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));','std::env::set_var("DECKCRAFT_FONT_IMPORT_ROOT", &base);\n        std::env::set_var("XDG_DATA_HOME", home.join(".local/share"));')
p.write_text(s)
p=root/'source/deckcraft/crates/ui-egui/src/lib.rs';s=p.read_text();s=s.replace('std::env::var_os("XDG_DATA_HOME").or_else', 'std::env::var_os("DECKCRAFT_FONT_IMPORT_ROOT").or_else(|| std::env::var_os("XDG_DATA_HOME")).or_else');p.write_text(s)
p=root/'templates/android/SafActivity.java';s=p.read_text();assert 'dispatchKeyEvent(' not in s;s=s.rstrip();assert s.endswith('}');p.write_text(s[:-1]+(here/'dcs_java.inc').read_text()+'\n}\n')
shutil.copy2(here/'dcs_bridge.rs',root/'templates/android/dcs_bridge.rs')
p=root/'lib/build-common.sh';s=p.read_text()
a=s.index('    "deckcraft": {');b=s.index('    "gridcraft": {',a);part=s[a:b]
def once(old,new):
 global part
 if part.count(old)!=1:raise ValueError('DeckCraft host anchor changed '+old[:60])
 part=part.replace(old,new,1)
once('    saves: Mutex<HashMap<u64, Vec<u8>>>,','    saves: Mutex<HashMap<u64, Vec<u8>>>,\n    close_requests: Mutex<HashMap<u64,u64>>,')
once('    let save_state = Arc::clone(&state);','    let save_state = Arc::clone(&state);\n    let close_state = Arc::clone(&state);\n    let close_bridge = bridge.clone_ref();\n    let close_inbox = inbox.clone();')
once('        download: Some(Box::new', '''        android_save_close: Some(Box::new(move |request, name, bytes| {
            let id = saf_next_id(&close_state);
            close_state.saves.lock().unwrap_or_else(|e| e.into_inner()).insert(id, bytes.to_vec());
            close_state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).insert(id, request);
            if close_bridge.request_save(id, name).is_err() {
                close_state.saves.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                close_state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                close_inbox.lock().unwrap_or_else(|e| e.into_inner()).push(InboxEvent::AndroidSaveFinished {id:request,success:false});
            }
        })),
        download: Some(Box::new''')
once('        match (kind, status) {','''        if kind == "save" {
            let request = state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
            if let Some(request) = request {
                let bytes = state.saves.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                let success = status == "ok" && match (bytes, value.get("path").and_then(serde_json::Value::as_str)) {
                    (Some(bytes), Some(path)) => saf_write_and_commit(bridge,path,&bytes).is_ok(),
                    _ => false,
                };
                inbox.lock().unwrap_or_else(|e| e.into_inner()).push(InboxEvent::AndroidSaveFinished {id:request,success});
                continue;
            }
        }
        match (kind, status) {''')
s=s[:a]+part+s[b:]
anchor='    (staging_dir / "src" / "lib.rs").write_text(entry)'
assert s.count(anchor)==1
injection='''    if app == "deckcraft":
        replacements = {
            'mod system_fonts;': 'mod dcs_bridge;\\nmod system_fonts;',
            'struct AndroidShell {': 'struct AndroidShell {\\n    dk: dcs_bridge::ModalBridge,',
            'let ime = ime_bridge::ime::ImeBridge::new(&app);': 'let dk = dcs_bridge::ModalBridge::new(&app);\\n        let ime = ime_bridge::ime::ImeBridge::new(&app);',
            'Self { inner, app, ime,': 'Self { inner, app, ime, dk,',
            '        self.inner.logic(ctx);': '        self.inner.android_capture_unsaved_dcs(ctx);\\n        self.dk.unsaved_dialog(self.inner.android_unsaved_dcs_active(),ctx);\\n        self.inner.logic(ctx);',
            '        self.inner.ui(ui);': '        self.inner.ui(ui);\\n        self.dk.unsaved_dialog(self.inner.android_unsaved_dcs_active(),ui.ctx());',
        }
        for before, after in replacements.items():
            if entry.count(before) != 1: raise ValueError('DeckCraft shell anchor changed: '+before)
            entry = entry.replace(before,after,1)
        shutil.copy2(root / 'templates/android/dcs_bridge.rs',staging_dir / 'src/dcs_bridge.rs')
'''
s=s.replace(anchor,injection+anchor);p.write_text(s)
