"""Android.13 heavy imported .ai performance: guarded Android-only selection budget.

This only modifies the disposable builder's checked-out VectorCraft v0.24.1 UI.
It never alters the underlying document, fonts, exports, undo history, raster
quality, GPU backend, stylus input or the published APK.
Upstream already implements raster caching and an off-thread render worker:
do not duplicate them. Limit the UI-thread mesh/anchor overlay work when a
complex group is selected, while retaining its bounding box and exact document
data. Add privacy-safe timings to distinguish the selection and panel costs.
"""
from pathlib import Path
import argparse

MARKER = "VC_ANDROID13_HEAVY_AI"

OUTLINE_BEFORE = "pub(super) const OVERLAY_MAX_ANCHORS: usize = 100_000;"
OUTLINE_AFTER = """// VC_ANDROID13_HEAVY_AI: lower only the selection/hover display budget on
// Android to avoid generating huge UI meshes for complex imported .ai groups.
// This affects only on-screen selection outlines; not artwork, hit testing,
// editing, text, image fidelity, saving, printing or exports.
#[cfg(target_os = "android")]
pub(super) const OVERLAY_MAX_ANCHORS: usize = 8_000;
#[cfg(not(target_os = "android"))]
pub(super) const OVERLAY_MAX_ANCHORS: usize = 100_000;"""

CANVAS_BEFORE = """        let overlays = selection_visuals(app, &painter, &xf, (hidden_chars, selection_marks, hover_still), revolve_edit, view_info);
        draw_overlays(&painter, &xf, &overlays, &t, HandleLook::of(&app.session.prefs));"""
CANVAS_AFTER = """        // VC_ANDROID13_HEAVY_AI: monitor only elapsed times, never file names,
        // text, coordinates or imported file content.
        #[cfg(target_os = "android")]
        let vc_selection_started = std::time::Instant::now();
        let overlays = selection_visuals(app, &painter, &xf, (hidden_chars, selection_marks, hover_still), revolve_edit, view_info);
        #[cfg(target_os = "android")]
        if vc_selection_started.elapsed() >= std::time::Duration::from_millis(24) {
            log::warn!("VC_PERF_SELECTION_OVERLAY elapsed_ms={} (no document content)", vc_selection_started.elapsed().as_millis());
        }
        draw_overlays(&painter, &xf, &overlays, &t, HandleLook::of(&app.session.prefs));"""

APP_BEFORE = """        egui::CentralPanel::default().frame(egui::Frame::NONE.fill(t.pasteboard)).show(ui, |ui| panel_docking::show(self, ui));
        crate::doc_windows::show(self, &ctx);"""
APP_AFTER = """        // VC_ANDROID13_HEAVY_AI: include canvas and docked panels in the
        // displayed UI-pass timing. Compare with the narrower selection timer
        // and existing renderer timing to locate the real bottleneck.
        #[cfg(target_os = "android")]
        let vc_panel_started = std::time::Instant::now();
        egui::CentralPanel::default().frame(egui::Frame::NONE.fill(t.pasteboard)).show(ui, |ui| panel_docking::show(self, ui));
        #[cfg(target_os = "android")]
        if vc_panel_started.elapsed() >= std::time::Duration::from_millis(30) {
            log::warn!("VC_PERF_DOCKED_PANELS elapsed_ms={} (includes canvas, no document content)", vc_panel_started.elapsed().as_millis());
        }
        crate::doc_windows::show(self, &ctx);"""

REPLACEMENTS = (
    ("source/vectorcraft/crates/ui-egui/src/canvas/outline.rs", OUTLINE_BEFORE, OUTLINE_AFTER),
    ("source/vectorcraft/crates/ui-egui/src/canvas.rs", CANVAS_BEFORE, CANVAS_AFTER),
    ("source/vectorcraft/crates/ui-egui/src/app.rs", APP_BEFORE, APP_AFTER),
)


def patch(root: Path) -> None:
    prepared = []
    for filename, before, after in REPLACEMENTS:
        target = root / filename
        source = target.read_text()
        if source.count(before) != 1 or MARKER in source:
            raise ValueError(f"STOP: pinned VectorCraft v0.24.1 source mismatch or already patched: {filename}")
        prepared.append((target, source.replace(before, after, 1)))
    # Fail closed on all three anchors before changing the disposable checkout.
    for target, updated in prepared:
        target.write_text(updated)
    print("PASS: Android-only complex group selection overlay cap plus privacy-safe UI timings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("builder", type=Path)
    patch(parser.parse_args().builder)
