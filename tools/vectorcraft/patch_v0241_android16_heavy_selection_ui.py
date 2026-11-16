"""VectorCraft Android.16 heavy selected-group UI improvements, tested on an isolated APK.

Baseline: successful Android.14 branch (never Android.15).
- Count a complex group's visible anchors once per unchanged document+selection
  instead of walking the nested group every UI frame.
- On Android, cap selection overlay complexity at 2,048 instead of 8,000.
- Once above that limit, render the existing selection and key bounding boxes
  but avoid the retained per-path outline mesh/metadata refresh altogether.

No changes to vector geometry, document model, export, AI links, brush/input,
Undo/Redo, native Vulkan limits, or the published app. Guard every source
anchor before touching the ephemeral builder. Desktop behavior is unchanged.
"""
from pathlib import Path
import argparse

MARKER = "VC_ANDROID16_HEAVY_SELECTION_UI"

OUTLINE_FILE = "source/vectorcraft/crates/ui-egui/src/canvas/outline.rs"
OVERLAYS_FILE = "source/vectorcraft/crates/ui-egui/src/canvas/overlays.rs"
MARKS_FILE = "source/vectorcraft/crates/ui-egui/src/canvas/selection_marks.rs"

# Android.13 already installed the reviewed Android-only 8k budget.
OLD_LIMIT = 'pub(super) const OVERLAY_MAX_ANCHORS: usize = 8_000;'
NEW_LIMIT = '''// VC_ANDROID16_HEAVY_SELECTION_UI: cap Android on-screen selection mesh work.
// This never changes node/anchor data, hit testing, export or desktop behavior.
pub(super) const OVERLAY_MAX_ANCHORS: usize = 2_048;'''

OLD_OVERLAY = '''    let big = show_marks && st.is_some_and(|st| too_many_anchors(st.selection.objects.iter().filter_map(|id| st.doc.node(*id))));'''
NEW_OVERLAY = '''    // VC_ANDROID16_HEAVY_SELECTION_UI: a nested group of thousands of paths
    // need not have its anchor count recalculated for every pan/zoom/UI frame.
    // The cache key includes the document UID, revision and selected object IDs,
    // so selecting another group, editing/undoing, or changing documents invalidates.
    let big = show_marks && st.is_some_and(|st| {
        #[cfg(target_os = "android")]
        { android16_large_selection(st, p.ctx()) }
        #[cfg(not(target_os = "android"))]
        { too_many_anchors(st.selection.objects.iter().filter_map(|id| st.doc.node(*id))) }
    });'''

OLD_KEY = '''            Some((k, n)) if too_many_anchors([n]) => (Some((k, n)), None),'''
NEW_KEY = '''            // VC_ANDROID16_HEAVY_SELECTION_UI: large groups keep their key
            // object's accurate box; do not rebuild huge key outlines on Android.
            Some((k, n)) if (cfg!(target_os = "android") && big) || too_many_anchors([n]) => (Some((k, n)), None),'''

OLD_PAINT = '''        marks.paint(st, p, xf, &options, key_outline, if big { &[] } else { &st.selection.objects });'''
NEW_PAINT = '''        // VC_ANDROID16_HEAVY_SELECTION_UI: the bounding box is already drawn
        // above. On very large Android selections skip all per-object mesh work,
        // including symbol bounds assembly, even on later idle frames.
        if cfg!(target_os = "android") && big {
            marks.clear_for_complex_selection();
        } else {
            marks.paint(st, p, xf, &options, key_outline, if big { &[] } else { &st.selection.objects });
        }'''

HELPER_ANCHOR = '''/// The selection's bounding box'''
# Insert before the selection_overlay function, a precise single-use source anchor.
FUNC_ANCHOR = '''pub(super) fn selection_overlay(app: &mut VectorcraftApp, p: &egui::Painter, xf: &Xf, curve_points_from_tool: bool, marks: &mut SelectionMarks) {'''
HELPER = '''// VC_ANDROID16_HEAVY_SELECTION_UI: cache the costly nested-group anchor
// complexity check independently of zoom, pan and display refresh. One cache
// entry per egui context is sufficient; document UID/revision and selection IDs
// are checked on every lookup. Only a boolean and IDs are stored, never art.
#[cfg(target_os = "android")]
fn android16_large_selection(st: &vectorcraft_engine::DocState, ctx: &egui::Context) -> bool {
    type Snapshot = ((u64, u64, Vec<u64>), bool);
    let key = (
        st.uid,
        st.revision,
        st.selection.objects.iter().map(|id| id.0).collect::<Vec<u64>>(),
    );
    let id = egui::Id::new("vc-android16-large-selection");
    if let Some((cached_key, big)) = ctx.data(|d| d.get_temp::<Snapshot>(id)) {
        if cached_key == key {
            return big;
        }
    }
    let big = too_many_anchors(st.selection.objects.iter().filter_map(|id| st.doc.node(*id)));
    ctx.data_mut(|d| d.insert_temp(id, (key, big)));
    big
}

'''

MARKS_CLEAR_ANCHOR = '''    fn clear(&mut self) {
        *self = Self {'''
MARKS_CLEAR_REPLACEMENT = '''    // VC_ANDROID16_HEAVY_SELECTION_UI: the caller paints the accurate selected
    // bounds instead of huge per-path marks, so drop any retained old mesh.
    // Keep test counters and leave small selections' normal cached paths intact.
    pub(super) fn clear_for_complex_selection(&mut self) {
        if self.look.is_some() || !self.objects.is_empty() || self.key.is_some() {
            self.clear();
        }
    }

    fn clear(&mut self) {
        *self = Self {'''

TEST_ANCHOR = '''/// Whether \`nodes\` have more than [\`OVERLAY_MAX_ANCHORS\`] points to outline'''
# Note TEST_ANCHOR is deliberately optional for the patch; the exact budget is
# checked by the source gate and existing UI test suite.

REPLACEMENTS = (
    (OUTLINE_FILE, ((OLD_LIMIT, NEW_LIMIT),)),
    (OVERLAYS_FILE, (
        (FUNC_ANCHOR, HELPER + FUNC_ANCHOR),
        (OLD_OVERLAY, NEW_OVERLAY),
        (OLD_KEY, NEW_KEY),
        (OLD_PAINT, NEW_PAINT),
    )),
    (MARKS_FILE, ((MARKS_CLEAR_ANCHOR, MARKS_CLEAR_REPLACEMENT),)),
)


def patch(root: Path):
    ready = []
    for filename, changes in REPLACEMENTS:
        path = root / filename
        text = path.read_text()
        if MARKER in text:
            raise ValueError(f"STOP: already applied: {filename}")
        for old, new in changes:
            if text.count(old) != 1:
                raise ValueError(f"STOP: unreviewed upstream/Android.14 source anchor in {filename}: {old[:60]!r}")
            text = text.replace(old, new, 1)
        ready.append((path, text))
    # Only write after validating all three sources. This cannot modify the
    # published repository; the caller's root is the temporary builder checkout.
    for path, text in ready:
        path.write_text(text)
    print("PASS: Android.16 heavy-group UI cache and bounded selection outlines installed; Android.14 rendering untouched")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("builder", type=Path)
    patch(ap.parse_args().builder)
