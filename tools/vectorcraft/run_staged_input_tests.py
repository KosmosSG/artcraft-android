from pathlib import Path
import subprocess,sys,tempfile
root=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='vc-input-tests-') as folder:
    p=Path(folder);(p/'src').mkdir()
    (p/'src/lib.rs').write_text((root/'adapters/vectorcraft/src/android_modifiers.rs').read_text())
    (p/'Cargo.toml').write_text('''[package]
name="vc-input-tests"
version="0.1.0"
edition="2024"
[dependencies]
egui={git="https://github.com/storytold/egui.git",rev="6d518fc799681571963842f95b55a6b68431b15a"}
''')
    subprocess.run(['cargo','test','--manifest-path',str(p/'Cargo.toml')],check=True)
