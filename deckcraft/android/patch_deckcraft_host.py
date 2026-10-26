"""Patch the isolated pinned builder only; add manual Android update service."""
from pathlib import Path
import sys
root = Path(sys.argv[1])
def edit(path, old, new):
    p = root / path
    s = p.read_text()
    assert s.count(old) == 1, (path, old)
    p.write_text(s.replace(old, new))
p = root / 'templates/android/saf_bridge.rs'
s = p.read_text()
a = s.index('        pub fn request_open(')
b = s.index('        pub fn request_save(', a)
method = s[a:b].replace('request_open(&self, id: u64, multiple: bool)', 'check_deckcraft_updates(&self)').replace('jni_str!("safRequestOpen")', 'jni_str!("deckCheckUpdates")').replace('jni_sig!("(JZ)V")', 'jni_sig!("()V")').replace('&[JValue::Long(id as i64), JValue::Bool(multiple)]', '&[]')
p.write_text(s[:a] + method + s[a:])
edit('lib/build-common.sh', '// DeckCraft hands us the request id it already tracks; echo it back on completion.', '''if _purpose == "deckcraft-updates" {
                if let Err(error) = open_bridge.check_deckcraft_updates() {
                    log::error!("Could not start update check: {error}");
                }
                return;
            }
            // DeckCraft hands us the request id it already tracks; echo it back on completion.''')
java = Path(__file__).with_name('DeckCraftUpdates.java.inc').read_text()
edit('templates/android/SafActivity.java', '    private static final String TAG = "__TAG__";', java + '\n    private static final String TAG = "__TAG__";')
edit('templates/android/SafActivity.java', '        super.onActivityResult(requestCode, resultCode, data);', '        super.onActivityResult(requestCode, resultCode, data);\n        if (requestCode == DECK_SAVE_UPDATE) { deckSaveUpdate(resultCode, data); return; }')
edit('lib/android_project.py', '    application = android_meta.get("application") or {}', '''    lines.append('    <uses-permission android:name="android.permission.INTERNET" />')
    application = android_meta.get("application") or {}''')
