"""Stage DeckCraft 0.14.1 on the latest reviewed Android builder without release signing."""
from pathlib import Path
import sys, subprocess
from patch_deckcraft_v013 import apply
root = Path(sys.argv[1]).resolve()
here = Path(__file__).parent.resolve()
apply(root/'source/deckcraft')
subprocess.run([sys.executable,str(here/'patch_deckcraft_host.py'),str(root)],check=True)
# Reuse the reviewed Android.4 save acknowledgement transport. Upstream source and font
# environment are ported separately because the latest builder already has writable font links.
s = (here/'patch_dcs_host.py').read_text()
s = s[s.index("p=root/'templates/android/SafActivity.java'"):]
exec(compile(s, str(here/'patch_dcs_host.py'), 'exec'), {'root':root,'here':here,'Path':Path,'shutil':__import__('shutil')})
p=root/'templates/android/system_fonts.rs';s=p.read_text()
old='std::env::set_var("XDG_DATA_HOME", &base);'
assert s.count(old)==1
p.write_text(s.replace(old,'std::env::set_var("DECKCRAFT_FONT_IMPORT_ROOT", &base);\n        '+old))
# Match desktop AutoRecover initialization; persistence tick writes snapshots before exit.
p=root/'lib/build-common.sh';s=p.read_text()
old='''        "save": ''' + "'''@UI@::settings::save(dir, &inner.ui, &inner.session.prefs);'''"
new='''        "save": ''' + "'''@UI@::settings::save(dir, &inner.ui, &inner.session.prefs);\n    let _ = inner.session.execute(\"file.recovery.save\", &serde_json::json!({}));'''"
assert s.count(old)==1;s=s.replace(old,new)
old='''    "deckcraft": {
        "load": ''' + "'''let (ui, prefs) = @UI@::settings::load(dir);"
new='''    "deckcraft": {
        "load": ''' + "'''inner.session.recovery_dir = Some(dir.join(\"recovery\"));\n    let _ = inner.session.execute(\"file.recovery.open\", &serde_json::json!({}));\n    let (ui, prefs) = @UI@::settings::load(dir);"
assert s.count(old)==1;s=s.replace(old,new)
p.write_text(s)
# The pinned builder uses the one-argument raw_input_hook for older UI apps.
# Official DeckCraft v0.14.1 requires (ctx, raw); keep this app-specific
# adaptation inside the disposable builder and leave other apps untouched.
p = root / 'lib/build-common.sh'
s = p.read_text()
old = 'inner_hook = "let _ = ctx;\\n        self.inner.raw_input_hook(raw);"'
new = 'inner_hook = ("self.inner.raw_input_hook(ctx, raw);" if app == "deckcraft" else "let _ = ctx;\\n        self.inner.raw_input_hook(raw);")'
assert s.count(old) == 1, 'Raw-input hook adapter changed'
p.write_text(s.replace(old, new, 1))

# DeckCraft-specific key handling. Run it in the generated raw-input hook
# BEFORE the UI and its modal keyboard routing; native Android dispatch can
# bypass the Java Activity's dispatchKeyEvent callback.
p = root / 'lib/build-common.sh'
s = p.read_text()
before = '        self.map_android_back(raw);'
after = '        self.map_android_back(raw);\n        self.inner.android_capture_unsaved_dcs_raw(ctx, raw);\n        self.inner.android_capture_editor_close_raw(ctx, raw);'
assert s.count(before) == 1, 'Android raw-key hook changed'
s = s.replace(before, after, 1)

# The reference builder normally exits the Activity when Back becomes Escape
# and the input is not consumed. DeckCraft must NEVER exit while a document is
# open: Esc/Back belongs first to text editing, dialogs, and the document UI.
before = '''        if self.back_pending {{
            self.back_pending = false;
            // A back press was mapped onto Escape.'''
after = '''        if self.back_pending {{
            self.back_pending = false;
            // Never close DeckCraft from Esc/Back with an open presentation.
            // The inner app has already processed Escape (including text exit).
            if self.inner.session.active().is_some() {{
                self.close_asked = false;
                return;
            }}
            // A back press was mapped onto Escape.'''
assert s.count(before) == 1, 'Android Back exit guard changed'
s = s.replace(before, after, 1)
p.write_text(s)

print('DeckCraft 0.14.1 host: D/C/S transport, persistent fonts and AutoRecover staged')

p=root/'source/deckcraft/crates/ui-egui/src/lib.rs'
p.write_text(p.read_text()+(here/'session.rs').read_text())
p=root/'lib/build-common.sh';s=p.read_text()
anchor='    let (ui, prefs) = @UI@::settings::load(dir);'
assert s.count(anchor)==1
s=s.replace(anchor,'    inner.android_restore_session(dir);\n'+anchor)
anchor='@UI@::settings::save(dir, &inner.ui, &inner.session.prefs);'
assert s.count(anchor)==1
s=s.replace(anchor,anchor+'\n    if let Err(error) = inner.android_save_session(dir) { log::warn!("Session persistence: {error}"); }')
p.write_text(s)
