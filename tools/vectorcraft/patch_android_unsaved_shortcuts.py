"""Patch only upstream VectorCraft v0.14 Save Changes dialog for Android hardware keys.

The patch targets the shared modal frame, preserving its normal save/discard/cancel
callbacks and preventing these keys from becoming canvas/type shortcuts.
"""
from pathlib import Path
import sys

OLD = '''    if spec.ok.is_some() && ok_enabled && !after_panel && ctx.input(|i| i.key_pressed(egui::Key::Enter)) {
        ok = true;
    }
    if discard {
'''
NEW = '''    // Android physical keyboard mnemonics for the unsaved-document dialog.
    // Run AFTER modal widgets have been drawn, but BEFORE saving d back to app.
    // Only the actual Save Changes dialog may capture these keys.
    if d.kind == crate::unsaved::KIND && !after_panel
        && !egui::Popup::is_any_open(ctx)
    {
        // A stale focused Type editor must NOT disable the modal hotkeys.
        // Consume eligible *physical key events* before the canvas gets them.
        // Do not treat text/IME composition commits as accelerator keys.
        let pressed = |key| ctx.input_mut(|i| i.consume_key(egui::Modifiers::NONE, key));
        if pressed(egui::Key::C) || pressed(egui::Key::Escape) {
            cancel = true;
        } else if pressed(egui::Key::D) {
            discard = true;
        } else if ok_enabled && pressed(egui::Key::S) {
            ok = true;
        }
    }
    if spec.ok.is_some() && ok_enabled && !after_panel && ctx.input(|i| i.key_pressed(egui::Key::Enter)) {
        ok = true;
    }
    if discard {
'''

def patch(root: Path) -> None:
    dialogs = root / "crates/ui-egui/src/dialogs/mod.rs"
    source = dialogs.read_text()
    if source.count(OLD) != 1:
        raise RuntimeError("Unreviewed upstream modal code; refusing to patch")
    if "Android physical keyboard mnemonics for the unsaved-document dialog." in source:
        raise RuntimeError("Patch already applied")
    source = source.replace(OLD, NEW)
    # Labels are scoped to the unsaved modal; every other dialog remains unchanged.
    labels = {
        'widgets::primary_button_enabled(ui, label, ok_enabled).clicked()':
            'widgets::primary_button_enabled(ui, if d.kind == crate::unsaved::KIND { "Save (S)" } else { label }, ok_enabled).clicked()',
        'widgets::secondary_button(ui, if spec.ok.is_some() { "Cancel" } else { "Close" }).clicked()':
            'widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND { "Cancel (C)" } else if spec.ok.is_some() { "Cancel" } else { "Close" }).clicked()',
        'discard = widgets::secondary_button(ui, label).clicked();':
            'discard = widgets::secondary_button(ui, if d.kind == crate::unsaved::KIND { "Don\'t Save (D)" } else { label }).clicked();',
    }
    for before, after in labels.items():
        if source.count(before) != 1:
            raise RuntimeError(f"Unexpected upstream dialog label site: {before}")
        source = source.replace(before, after)
    dialogs.write_text(source)
    save = root / "crates/ui-egui/src/dialogs/save_changes.rs"
    expected = ('ok: Some("Save"),', 'discard: Some("Don\'t Save"),',
                'confirm: |app, _| crate::unsaved::confirm(app),')
    if not all(term in save.read_text() for term in expected):
        raise RuntimeError("Upstream unsaved dialog contract changed")

if __name__ == "__main__":
    patch(Path(sys.argv[1]))
