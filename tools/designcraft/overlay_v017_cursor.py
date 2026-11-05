#!/usr/bin/env python3
"""DesignCraft-only v0.17 Android adaptive pointer (MostafaXS1 v0.2.0, MIT).

Modify ONLY DesignCraft's throwaway upstream checkout after the builder vendors
its egui-winit. No suite-wide vendor file or production key is modified.
"""
from pathlib import Path
import sys
import shutil


def once(s, old, new, where):
    count = s.count(old)
    if count != 1:
        raise ValueError(f"{where}: expected one anchor, found {count}: {old[:80]!r}")
    return s.replace(old, new, 1)


def apply(root: Path, egui_winit: Path):
    if egui_winit.name != "egui-winit" or egui_winit.parent.name != "vendor":
        raise ValueError("Not a builder-staged egui-winit source")
    if egui_winit.parent.parent.name != "designcraft":
        raise ValueError("Refusing to modify a non-DesignCraft checkout")
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
    # The pinned Android backend implements reset_ime_with_request as a no-op.
    # A reset acknowledgement is a notification, never text or a physical key.
    anchor = "            WindowEvent::Ime(ime) => {"
    source = once(source, anchor, """            WindowEvent::ImeResetCompleted { .. } => EventResponse {
                repaint: false,
                consumed: false,
            },
""" + anchor, str(lib))
    anchor = '        WindowEvent::Ime { .. } => "WindowEvent::Ime",'
    source = once(source, anchor, anchor + '\n        WindowEvent::ImeResetCompleted { .. } => "WindowEvent::ImeResetCompleted",', str(lib))
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
    if len(sys.argv) != 3:
        raise SystemExit("usage: overlay_v017_cursor.py REPO_ROOT DESIGNCRAFT_EGUI_WINIT")
    apply(*(Path(x).resolve() for x in sys.argv[1:]))
