"""Cheap no-NDK source checks for Android.10 imported live-text edit recovery."""
from pathlib import Path
from tempfile import TemporaryDirectory
from patch_android10_imported_ai_text import OLD, NEW, patch

with TemporaryDirectory(prefix='vc-android10-text-hit-') as folder:
    file = Path(folder) / 'source/vectorcraft/crates/tools/src/text.rs'
    file.parent.mkdir(parents=True)
    file.write_text('use vectorcraft_doc::TextKind;\n        #[cfg(target_os = "android")]\n        let text_id = h.and_then(|hit| {\n' + OLD + '\nlet text_id = h?.leaf;\n')
    patch(Path(folder))
    amended = file.read_text()
    assert OLD not in amended
    assert NEW in amended
    assert 'NodeKind::Text(t)' in amended
    assert 'is_editable_with(&cx.doc.locked_artboards(), *id)' in amended
    assert 'let text_id = h?.leaf;' in amended
    assert 'node.geometric_bounds()' in amended
    assert 'sibling_hit' in amended
    assert 'let top_hit_parent = h.as_ref()' in amended
    assert 'TextKind::Area { frame }' in amended
    try:
        patch(Path(folder))
    except RuntimeError:
        pass
    else:
        raise AssertionError('duplicate overlay did not fail closed')
print('PASS: Android.10 text hit overlay idempotency guard, editable-only, no desktop edits')
