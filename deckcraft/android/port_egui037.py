"""Retain official egui 0.37 fixes while porting the builder's Android-only bridges."""
from pathlib import Path
import shutil, subprocess, sys, tomllib
import toml
root, egui, winit = map(Path, sys.argv[1:])
old = root/'vendor/egui-winit'
custom = {name:(old/'src'/name).read_text() for name in ['android_activity.rs','open_url.rs','pointer_icon.rs','system_theme.rs']}
clipboard=(old/'src/clipboard.rs').read_text()
shutil.rmtree(old)
shutil.copytree(egui/'crates/egui-winit',old)
workspace=tomllib.loads((egui/'Cargo.toml').read_text())['workspace']
m=tomllib.loads((old/'Cargo.toml').read_text())
for key,value in list(m['package'].items()):
 if isinstance(value,dict) and value.get('workspace'):m['package'][key]=workspace['package'][key]
m.pop('lints',None)
def normalize(deps):
 for name,value in list(deps.items()):
  if isinstance(value,dict) and value.get('workspace'):
   base=workspace['dependencies'][name]
   base={'version':base} if isinstance(base,str) else dict(base)
   features=base.get('features',[])+value.get('features',[])
   base.update({k:v for k,v in value.items() if k!='workspace'})
   base.pop('path',None)
   if features:base['features']=list(dict.fromkeys(features))
   deps[name]=base
for kind in ['dependencies','dev-dependencies','build-dependencies']:normalize(m.get(kind,{}))
for table in m.get('target',{}).values():
 for kind in ['dependencies','dev-dependencies','build-dependencies']:normalize(table.get(kind,{}))
m.setdefault('target',{}).setdefault('cfg(target_os = "android")',{}).setdefault('dependencies',{}).update({'jni':'0.22.4','ndk-context':'0.1.1','android-activity':{'version':'0.6.4','features':['game-activity']}})
(old/'Cargo.toml').write_text(toml.dumps(m))
for name,content in custom.items():(old/'src'/name).write_text(content)
subprocess.run(['git','apply','--unsafe-paths',str(Path(__file__).with_name('egui-winit-037-android.patch').resolve())],cwd=old,check=True)
p=old/'src/clipboard.rs';s=p.read_text()
for anchor,extra in [
 ('    pub fn get(&mut self) -> Option<String> {','\n        #[cfg(target_os = "android")]\n        if let Some(text) = android_clipboard_get_text() { return Some(text); }'),
 ('    pub fn set_text(&mut self, text: String) {','\n        #[cfg(target_os = "android")]\n        if android_clipboard_set_text(&text) { return; }')]:
 assert s.count(anchor)==1;s=s.replace(anchor,anchor+extra)
s += '\n'+clipboard[clipboard.index('/// Android clipboard via JNI'):];p.write_text(s)
# Keep the official winit desktop/IME changes, replacing only its Android backend later.
dest=root/'source/deckcraft/vendor/winit'
if dest.exists():shutil.rmtree(dest)
shutil.copytree(winit,dest,ignore=shutil.ignore_patterns('.git'))
p=root/'lib/build-common.sh';s=p.read_text();assert s.count('egui-winit = "0.36"')==1
s=s.replace('egui-winit = "0.36"','egui-winit = "0.37"')
# The official source is already on wgpu 30; never substitute the builder's wgpu 27 module.
a=s.index('echo "Vendoring the surface-fixing egui-wgpu');b=s.index('\nPY',a)+3
s=s[:a]+'# Keep the pinned official egui-wgpu 0.37 implementation.\n'+s[b:]
p.write_text(s)

# Preserve the official Android backend's reset API (it is explicitly a no-op there;
# composition is owned by the existing Java IME bridge). The builder supplies mouse
# and scroll support, so copy these upstream declarations into that backend.
p=root/'vendor/winit/src/platform_impl/android/mod.rs';s=p.read_text()
anchor='    pub fn set_ime_allowed(&self, allowed: bool) {'
if anchor not in s:
    import re
    match=re.search(r'    pub fn set_ime_allowed\([^\n]+\{',s)
    if not match:raise ValueError('Android IME method changed')
    anchor=match.group(0)
assert 'pub fn reset_ime(' not in s
p.write_text(s.replace(anchor,'    pub fn reset_ime(&self) {}\n\n    pub fn reset_ime_with_request(&self, _request_id: u64) {}\n\n'+anchor,1))
