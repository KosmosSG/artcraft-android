"""Add Android-only native menu commands to the exact reviewed VectorCraft v0.14.0 UI.

The official Git checkout remains pinned. This overlay is applied in the disposable
build tree; it fails closed if either upstream file changes.
"""
import argparse
import hashlib
from pathlib import Path

PINS = {
    "menus.rs": "a2c706d8c87b2aa5207968d5e2419d9678c223fca539747976c08063bfd53945",
    "lib.rs": "00ce639ef28baabce2398c3952960e04b834475bb124895e8baa1c9c78190958",
}
COMMANDS = [
    ("android.importFont", "Import Font (.ttf / .otf)…"),
    ("android.selectFontFolder", "Select Shared Font Folder…"),
    ("android.refreshFonts", "Refresh Shared Fonts"),
    ("android.checkUpdates", "Check for Updates…"),
    ("android.startupUpdates", "Check for Updates at Startup"),
    ("android.settings", "Android Settings…"),
]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one reviewed UI anchor: {old[:70]}")
    return text.replace(old, new, 1)


def prepare(source):
    folder = Path(source) / "crates/ui-egui/src"
    texts = {}
    for name, expected in PINS.items():
        data = (folder / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Upstream {name} changed; review the Android menu overlay")
        texts[name] = data.decode()
    menu = texts["menus.rs"]
    anchor = 'pub const UI_COMMANDS: &[(&str, &str, &str, &str)] = &[\n'
    entries = ''.join(
        f'    #[cfg(target_os = "android")]\n    ("{key}", "{label}", "", "{{}} Android host command"),\n'
        for key, label in COMMANDS
    )
    menu = replace_once(menu, anchor, anchor + entries)
    anchor = 'pub fn run_ui_command(app: &mut VectorcraftApp, id: &str, p: &Value) -> Option<Result<Value, String>> {\n'
    menu = replace_once(menu, anchor, anchor + '''    #[cfg(target_os = "android")]
    if crate::android_commands::request(id) {
        return Some(Ok(json!({"android": id})));
    }
''')
    anchor = 'pub fn enabled(app: &VectorcraftApp, id: &str) -> bool {\n'
    menu = replace_once(menu, anchor, anchor + '''    #[cfg(target_os = "android")]
    if crate::android_commands::is_command(id) { return true; }
''')
    anchor = 'pub fn checked(app: &VectorcraftApp, id: &str, p: &Value) -> Option<bool> {\n'
    menu = replace_once(menu, anchor, anchor + '''    #[cfg(target_os = "android")]
    if let Some(value) = crate::android_commands::checked(id) { return Some(value); }
''')
    start = menu.index('pub fn menu_tree_named(')
    end = menu.index('\n/// Object → Transform', start)
    body = menu[start:end]
    body = replace_once(body, '\n    vec![\n', '\n    #[allow(unused_mut)]\n    let mut tree = vec![\n')
    tail = '''    ];
    #[cfg(target_os = "android")]
    for (title, items) in &mut tree {
        if *title == "Type" {
            items.insert(0, sub("Custom Fonts", vec![
                c("Import Font (.ttf / .otf)…", "android.importFont"),
                c("Select Shared Font Folder…", "android.selectFontFolder"),
                c("Refresh Shared Fonts", "android.refreshFonts"),
            ]));
            items.insert(1, Sep);
        }
        if *title == "Help" {
            items.splice(0..0, [
                c("Check for Updates…", "android.checkUpdates"),
                c("Check for Updates at Startup", "android.startupUpdates"),
                Sep,
            ]);
            items.extend([Sep, c("Android Settings…", "android.settings")]);
        }
    }
    tree
}
'''
    if not body.endswith('    ]\n}\n'):
        raise ValueError("Reviewed menu tree closing anchor changed")
    body = body[:-len('    ]\n}\n')] + tail
    menu = menu[:start] + body + menu[end:]
    lib = replace_once(texts["lib.rs"], 'pub mod menus;\n',
        'pub mod menus;\n#[cfg(target_os = "android")]\npub mod android_commands;\n')
    # All anchors and pins are checked before modifying any source file.
    (folder / "menus.rs").write_text(menu)
    (folder / "lib.rs").write_text(lib)
    bridge = Path(__file__).with_name("android_commands.rs").read_bytes()
    (folder / "android_commands.rs").write_bytes(bridge)
    print("PASS: Android Help update controls and Type > Custom Fonts are wired to the host")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    prepare(parser.parse_args().source)
