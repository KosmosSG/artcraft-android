"""DesignCraft-only SAF acknowledgement and writable font bootstrap in staging."""
from pathlib import Path
import sys
from patch_unsaved_dcs import apply
def patch(root):
 root=Path(root);apply(root/'source/designcraft')
 p=root/'lib/build-common.sh';s=p.read_text();a=s.index('    "designcraft": {');b=s.index('\n    "',a+10);part=s[a:b]
 def once(old,new):
  nonlocal part
  if part.count(old)!=1:raise ValueError('DesignCraft SAF anchor changed '+old[:60])
  part=part.replace(old,new,1)
 once('    saves: Mutex<HashMap<u64, Vec<u8>>>,','    saves: Mutex<HashMap<u64, Vec<u8>>>,\n    close_requests: Mutex<HashMap<u64,std::sync::mpsc::Sender<bool>>>,')
 once('    let save_state = Arc::clone(&state);','    let save_state = Arc::clone(&state);\n    let close_state = Arc::clone(&state);\n    let close_bridge = bridge.clone_ref();')
 once('        download: Some(Box::new', '''        android_save_close: Some(Box::new(move |name, bytes, reply| {
             let id = saf_next_id(&close_state);
             close_state.saves.lock().unwrap_or_else(|e| e.into_inner()).insert(id, bytes.to_vec());
             close_state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).insert(id, reply);
             if close_bridge.request_save(id, name).is_err() {
                 close_state.saves.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                 if let Some(reply)=close_state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) { let _=reply.send(false); }
             }
         })),
         download: Some(Box::new''')
 once('        match (kind, status) {','''        if kind == "save" {
             let reply = state.close_requests.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
             if let Some(reply) = reply {
                 let bytes = state.saves.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                 let success = status == "ok" && match (bytes, value.get("path").and_then(serde_json::Value::as_str)) {
                     (Some(bytes), Some(path)) => saf_write_and_commit(bridge,path,&bytes).is_ok(),
                     _ => false,
                 };
                 let _=reply.send(success);
                 continue;
             }
         }
         match (kind, status) {''')
 p.write_text(s[:a]+part+s[b:])
