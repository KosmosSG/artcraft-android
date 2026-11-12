"""Android-only Type hit recovery for selected Illustrator live text.

This overlay follows Android.8/9 (which already supply a selected-live-text
fallback). It changes no desktop behavior and neither converts nor edits paths.
The layout of a missing imported font can differ from the imported geometric
bounds, or the top hit can be another shape in the same icon group. In that
case permit a selected, editable Text node to receive an explicit Type click.
"""
from pathlib import Path
import sys

OLD = '''            cx.selection.objects.iter().copied().find(|id| {
                let Some(NodeKind::Text(t)) = cx.doc.node(*id).map(|n| &n.kind) else { return false };
                let local = t.xf.inverse() * p;
                self.layout(t).bounds.inflate(cx.tol(6.0), cx.tol(6.0)).contains(local)
            })'''

NEW = '''            // Imported Illustrator art often has a missing font and overlapping
            // icon/background paths. A substitute font changes layout.bounds:
            // use the document's own geometric bounds as well. If one editable
            // live Text is selected, also accept a click on an overlapping
            // sibling from the same group; do not redirect an empty-canvas click.
            cx.selection.objects.iter().copied().find(|id| {
                let Some(node) = cx.doc.node(*id) else { return false };
                let NodeKind::Text(t) = &node.kind else { return false };
                if !cx.doc.is_editable_with(&cx.doc.locked_artboards(), *id) {
                    return false;
                }
                let tol = cx.tol(8.0);
                let local = t.xf.inverse() * p;
                let layout_hit = self.layout(t).bounds.inflate(tol, tol).contains(local);
                let import_bounds_hit = node.geometric_bounds()
                    .is_some_and(|rect| rect.inflate(tol, tol).contains(p));
                let frame_hit = match &t.kind {
                    TextKind::Area { frame } => frame.bounds()
                        .is_some_and(|rect| rect.inflate(tol, tol).contains(local)),
                    _ => false,
                };
                let sibling_hit = cx.selection.objects.len() == 1
                    && top_hit_parent.zip(cx.doc.parent_of(*id))
                        .is_some_and(|(hit_parent, text_parent)| hit_parent == text_parent);
                layout_hit || import_bounds_hit || frame_hit || sibling_hit
            })'''


def patch(root: Path) -> None:
    target = root / 'source/vectorcraft/crates/tools/src/text.rs'
    source = target.read_text()
    if source.count(OLD) != 1:
        raise RuntimeError('Android.10 text hit preflight: expected one Android.8 selected-live-text fallback, found ' + str(source.count(OLD)))
    head = '        #[cfg(target_os = "android")]\n        let text_id = h.and_then(|hit| {'
    assert source.count(head) == 1, 'Android.10: native Type hit anchor missing'
    fixed = '        #[cfg(target_os = "android")]\n        let top_hit_parent = h.as_ref().and_then(|hit| cx.doc.parent_of(hit.leaf));\n' + head
    result = source.replace(head, fixed, 1).replace(OLD, NEW, 1)
    assert result.count('let text_id = h?.leaf') == 1, 'Desktop hit path changed unexpectedly'
    assert result.count('cx.doc.is_editable_with(&cx.doc.locked_artboards(), *id)') == 1
    assert result.count('TextKind::Area { frame }') >= 1
    target.write_text(result)
    print('PASS: Android.10 editable selected .ai live-text geometry/overlap Type hit recovery')


if __name__ == '__main__':
    patch(Path(sys.argv[1]))
