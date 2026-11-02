#!/usr/bin/env python3
"""Wire v0.15 GridCraft SAF Save Changes acknowledgements into the pinned Android generator.

Modifies ONLY the gridcraft entry of the disposable builder's SAF_RECIPES.
The generated Android app's existing save picker is reused; its callback sends
true only AFTER the chosen SAF destination has been written and committed.
No permanent signing keys, Android release, or other apps are touched.
"""
from pathlib import Path
import argparse
import json

MARKER = "GRIDCRAFT_V0150_ACK_SAF_V1"
PREFIX = 'SAF_RECIPES = {'
APP_START = '    "gridcraft": {'
APP_END = '\n    "wordcraft": {'


def once(s: str, old: str, new: str, where: str) -> str:
    n = s.count(old)
    if n != 1:
        raise RuntimeError(f"{where}: expected one stable GridCraft SAF recipe anchor, got {n}: {old[:130]!r}")
    return s.replace(old, new, 1)


def transform(builder_script: str) -> str:
    if MARKER in builder_script:
        raise RuntimeError("GridCraft v0.15 acknowledged save bridge already installed")
    start = builder_script.find(PREFIX)
    if start < 0:
        raise RuntimeError("Pinned builder SAF_RECIPE declaration missing")
    app_start = builder_script.find(APP_START, start + len(PREFIX))
    if app_start < 0:
        raise RuntimeError("Pinned builder GridCraft SAF recipe missing")
    app_end = builder_script.find(APP_END, app_start)
    if app_end < 0:
        raise RuntimeError("Pinned builder next-app boundary changed")
    recipe = builder_script[app_start:app_end]
    recipe = once(
        recipe,
        '    saves: Mutex<HashMap<u64, Vec<u8>>>,',
        '    saves: Mutex<HashMap<u64, Vec<u8>>>,\n'
        f'    // {MARKER}: one-shot reply for SAF save-and-close request.\n'
        '    save_acks: Mutex<HashMap<u64, std::sync::mpsc::Sender<bool>>>,',
        "GridCraft SafState"
    )
    recipe = once(
        recipe,
        '    let save_state = Arc::clone(&state);',
        '    let save_state = Arc::clone(&state);\n'
        '    let acknowledged_bridge = bridge.clone_ref();\n'
        '    let acknowledged_state = Arc::clone(&state);',
        "GridCraft saf_services",
    )
    recipe = once(
        recipe,
        '        inbox: Some(inbox),',
        '''        // ''' + MARKER + ''': report write results, not just save-picker success.
        android_save_close: Some(Box::new(move |name: &str, bytes: &[u8], reply: std::sync::mpsc::Sender<bool>| {
            let id = saf_next_id(&acknowledged_state);
            acknowledged_state.saves.lock().unwrap_or_else(|e| e.into_inner()).insert(id, bytes.to_vec());
            acknowledged_state.save_acks.lock().unwrap_or_else(|e| e.into_inner()).insert(id, reply);
            if let Err(error) = acknowledged_bridge.request_save(id, name) {
                log::error!("GridCraft: could not start SAF save-and-close: {error}");
                acknowledged_state.saves.lock().unwrap_or_else(|e| e.into_inner()).remove(&id);
                if let Some(reply) = acknowledged_state.save_acks.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) {
                    let _ = reply.send(false);
                }
            }
        })),
        inbox: Some(inbox),''',
        "GridCraft saf_services ack callback",
    )
    old_ok = '''            ("save", "ok") => {
                let bytes = state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
                if let Some(bytes) = bytes {
                    match value.get("path").and_then(serde_json::Value::as_str) {
                        Some(path) => {
                            if let Err(error) = saf_write_and_commit(bridge, path, &bytes) {
                                log::error!("Could not write the saved file: {error}");
                            }
                        }
                        None => log::error!("Android save picker returned no destination path"),
                    }
                }
            }'''
    new_ok = '''            ("save", "ok") => {
                let bytes = state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
                let success = match (bytes, value.get("path").and_then(serde_json::Value::as_str)) {
                    (Some(bytes), Some(path)) => {
                        match saf_write_and_commit(bridge, path, &bytes) {
                            Ok(()) => true,
                            Err(error) => {
                                log::error!("GridCraft SAF write/commit failed: {error}");
                                false
                            }
                        }
                    }
                    _ => {
                        log::error!("Android save picker returned no bytes or destination");
                        false
                    }
                };
                if let Some(reply) = state.save_acks.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) {
                    let _ = reply.send(success);
                }
            }'''
    recipe = once(recipe, old_ok, new_ok, "GridCraft saf_poll save ok")
    recipe = once(
        recipe,
        '''            ("save", "cancel") => {
                state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
            }''',
        '''            ("save", "cancel") => {
                state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
                if let Some(reply) = state.save_acks.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) {
                    let _ = reply.send(false);
                }
            }''',
        "GridCraft saf_poll save cancel",
    )
    recipe = once(
        recipe,
        '''                state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
            }
        }
    }
}''',
        '''                state.saves.lock().unwrap_or_else(|error| error.into_inner()).remove(&id);
                if let Some(reply) = state.save_acks.lock().unwrap_or_else(|e| e.into_inner()).remove(&id) {
                    let _ = reply.send(false);
                }
            }
        }
    }
}''',
        "GridCraft saf_poll malformed/error",
    )
    if recipe.count(MARKER) != 2:
        raise RuntimeError("Expected GridCraft-only SAF state and service markers")
    patched = builder_script[:app_start] + recipe + builder_script[app_end:]
    if not patched.startswith(builder_script[:app_start]) or not patched.endswith(builder_script[app_end:]):
        raise RuntimeError("Refusing to change other ArtCraft app recipes")
    return patched


def main():
    p = argparse.ArgumentParser()
    p.add_argument("builder_script", type=Path)
    p.add_argument("--verify-only", action="store_true")
    args = p.parse_args()
    path = args.builder_script.resolve()
    if path.name != "build-common.sh" or path.parent.name != "lib" or not (path.parent.parent / "build.sh").is_file():
        raise RuntimeError("Refusing to patch anything except a disposable Android builder checkout")
    original = path.read_text()
    patched = transform(original)
    if not args.verify_only:
        path.write_text(patched)
    print(json.dumps({
        "gridcraft_saf_acknowledged_close": True,
        "conserves_original_signed_release": True,
        "other_apps_unchanged": True,
        "builder_written": not args.verify_only,
        "actual_apk_compiled": False,
    }, indent=2))


if __name__ == "__main__":
    main()
