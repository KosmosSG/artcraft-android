#!/usr/bin/env python3
"""DesignCraft-only v0.17 Android adaptive pointer (MostafaXS1 v0.2.0, MIT).

Modify ONLY DesignCraft's throwaway upstream checkout after the builder vendors
its egui-winit. No suite-wide vendor file or production key is modified.
"""
from pathlib import Path
import sys
import shutil
import tomllib
import os


def once(s, old, new, where):
    count = s.count(old)
    if count != 1:
        raise ValueError(f"{where}: expected one anchor, found {count}: {old[:80]!r}")
    return s.replace(old, new, 1)


def apply(root: Path, egui_winit: Path, designcraft: Path):
    if designcraft.name != "designcraft" or egui_winit.parts[-3:] != ("designcraft-egui", "crates", "egui-winit"):
        raise ValueError("Expected DesignCraft and its pinned egui workspace")
    # eframe depends on its sibling egui-winit via a path. All egui packages
    # must resolve from this same workspace, including the launcher's JNI hook.
    workspace = designcraft / "Cargo.toml"
    manifest = workspace.read_text()
    pins = tomllib.loads(manifest)["patch"]["crates-io"]
    for name, dep in pins.items():
        if dep.get("git") == "https://github.com/storytold/egui.git":
            original = f'{name} = {{ git = "{dep["git"]}", rev = "{dep["rev"]}" }}'
            crate = egui_winit.parent / name
            if dep["rev"] != "6d518fc799681571963842f95b55a6b68431b15a" or not (crate / "Cargo.toml").is_file():
                raise ValueError(f"Unverified egui dependency: {name}")
            manifest = once(manifest, original, f'{name} = {{ path = "{os.path.relpath(crate, designcraft)}" }}', name)
    workspace.write_text(manifest)
    # Carry only the approved Android clipboard JNI routines into the locked
    # fork, preserving its complete IME, viewport, clipboard and key APIs.
    clipboard = egui_winit / "src/clipboard.rs"
    text = clipboard.read_text()
    donor = (root / "vendor/egui-winit/src/clipboard.rs").read_text()
    helpers = donor.split("/// Android clipboard via JNI", 1)[1].split("#[cfg(all(", 1)[0]
    text += "\n/// Android clipboard via JNI" + helpers
    for anchor, code in [
        ("    pub fn get(&mut self) -> Option<String> {", "if let Some(text) = android_clipboard_get_text() { return Some(text); }"),
        ("    pub fn set_text(&mut self, text: String) {", "if android_clipboard_set_text(&text) { return; }"),
    ]:
        text = once(text, anchor, anchor + '\n        #[cfg(target_os = "android")]\n        ' + code, str(clipboard))
    clipboard.write_text(text)
    cargo = egui_winit / "Cargo.toml"
    cargo.write_text(cargo.read_text() + """
[target.'cfg(target_os = "android")'.dependencies]
jni = "0.22.4"
ndk-context = "0.1.1"
""")
    src = egui_winit / "src"
    lib = src / "lib.rs"
    source = lib.read_text()
    source = once(source, "mod dropped_file;\n", '''mod dropped_file;
#[cfg(target_os = "android")]
pub mod android_activity;
#[cfg(target_os = "android")]
mod pointer_icon;
''', str(lib))
    source = once(
        source,
        '''        } else {
            window.set_cursor_visible(false);
        }
    }
}

fn to_egui_touch_phase''',
        '''        } else {
            window.set_cursor_visible(false);
        }
        // Preserve egui's dedupe; Android's system pointer changes only when
        // the UI-selected icon changes (text, clickable items, resize handles).
        #[cfg(target_os = "android")]
        crate::pointer_icon::apply(cursor_icon);
    }
}

fn to_egui_touch_phase''',
        str(lib),
    )
    if source.count("WindowEvent::ImeResetCompleted { .. } =>") != 2:
        raise ValueError("Locked IME-reset dispatch or diagnostic mapping is missing")
    for original, target in [
        ("fork_v020_adaptive_pointer_icon.rs", "pointer_icon.rs"),
        ("fork_v020_android_activity.rs", "android_activity.rs"),
    ]:
        donor = root / "tools" / "designcraft" / original
        if not donor.is_file() or (src / target).exists():
            raise ValueError(f"Missing source or destination already exists: {target}")
        shutil.copyfile(donor, src / target)
    lib.write_text(source)
    print("DesignCraft-only adaptive Android cursor mapped to system PointerIcon (MostafaXS1 v0.2.0)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: overlay_v017_cursor.py REPO_ROOT DESIGNCRAFT_EGUI_WINIT")
    apply(*(Path(x).resolve() for x in sys.argv[1:]))
