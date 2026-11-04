"""Android-only D/C/S Save Changes dialog overlay for VectorCraft v0.20.0.

The upstream modal frame moved from dialogs/mod.rs to dialogs.rs. Keep its
normal confirmation, discard and cancellation callbacks. Refuse unexpected
source changes instead of removing a tested keyboard feature.
"""
from pathlib import Path
import sys


def once(source: str, anchor: str, replacement: str, label: str) -> str:
    hits = source.count(anchor)
    if hits != 1:
        raise RuntimeError(f"Unreviewed v0.20 {label} anchor: expected 1, found {hits}")
    return source.replace(anchor, replacement, 1)


def patch(root: Path) -> None:
    manifest = (root / "Cargo.toml").read_text()
    if sum(manifest.count('version = "' + v + '"') for v in ('0.20.0', '0.21.0')) != 1:
        raise RuntimeError("Unsupported upstream for reviewed v0.20/v0.21 Save Changes patch")
    path = root / "crates/ui-egui/src/dialogs.rs"
    source = path.read_text()
    key = '''    if spec.ok.is_some() && ok_enabled && !after_panel && !rejected && ctx.input(|i| i.key_pressed(egui::Key::Enter)) {
        ok = true;
    }
    if discard {
'''
    patched = '''    // Android physical keyboard mnemonics for Save Changes only. Rejection by
    // an active modal/IME must not become a canvas command or typed text.
    #[cfg(target_os = "android")]
    if d.kind == crate::unsaved::KIND && !after_panel && !rejected
        && !egui::Popup::is_any_open(ctx)
    {
        // A physical Ctrl+W can leave Ctrl latched across the IME handoff.
        // consume_key(NONE) rejects the following D/C/S if modifiers linger.
        // Accept the key press only in the Save Changes dialog, and never
        // steal keystrokes from an active egui text-edit field.
        let pressed = |key| !ctx.text_edit_focused() && ctx.input(|i| i.key_pressed(key));
        if pressed(egui::Key::C) || pressed(egui::Key::Escape) {
            cancel = true;
        } else if pressed(egui::Key::D) {
            discard = true;
        } else if ok_enabled && pressed(egui::Key::S) {
            ok = true;
        }
    }
    if spec.ok.is_some() && ok_enabled && !after_panel && !rejected && ctx.input(|i| i.key_pressed(egui::Key::Enter)) {
        ok = true;
    }
    if discard {
'''
    source = once(source, key, patched, "modal keyboard action")
    source = once(source,
        'widgets::primary_button_enabled(ui, label, ok_enabled).clicked()',
        'widgets::primary_button_enabled(ui, if d.kind == crate::unsaved::KIND { "Save (S)" } else { label }, ok_enabled).clicked()',
        "Save label")
    source = once(source,
        'if widgets::secondary_button(ui, label).clicked() {\n                if resets {',
        'if widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND && !resets { "Cancel (C)" } else { label }).clicked() {\n                if resets {',
        "Cancel label")
    source = once(source,
        'discard = widgets::secondary_button(ui, label).clicked();',
        'discard = widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND { "Don\'t Save (D)" } else { label }).clicked();',
        "Discard label")
    save = root / "crates/ui-egui/src/dialogs/save_changes.rs"
    contract = save.read_text()
    for phrase in ('ok: Some("Save"),', 'discard: Some("Don\'t Save"),',
                   'confirm: |app, _| crate::unsaved::confirm(app),'):
        if phrase not in contract:
            raise RuntimeError(f"Save Changes callback contract differs: {phrase}")
    path.write_text(source)
    print("PASS: VectorCraft v0.20 Save Changes retains D/C/S and original callbacks")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
