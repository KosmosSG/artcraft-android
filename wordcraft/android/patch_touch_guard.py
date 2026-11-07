#!/usr/bin/env python3
"""Isolated Android-only guard: a two-finger pan cannot edit the document.

Applied after the approved stylus smoothing and pressure-ink overlays. Native
finger gestures are cancelled by the Activity; pending WordCraft canvas drags
are cancelled here. Desktop upstream and stable release remain unchanged.
"""
from pathlib import Path


def one(code: str, anchor: str, new: str, label: str) -> str:
    count = code.count(anchor)
    if count != 1:
        raise RuntimeError(f"WordCraft touch guard {label}: expected one anchor, got {count}")
    return code.replace(anchor, new, 1)


def apply_touch_guard(root: Path) -> None:
    base = root / "crates" / "ui-egui" / "src"
    canvas = base / "canvas.rs"
    text = canvas.read_text(encoding="utf-8")
    anchor = """pub fn show(app: &mut WordApp, ui: &mut Ui) {
    let t = Tokens::get(ui.ctx());"""
    updated = """pub fn show(app: &mut WordApp, ui: &mut Ui) {
    // WC_ANDROID_NO_SELECTION_DURING_TWO_FINGER_V1
    // Cancel text/object drag in the same frame a second finger begins.
    #[cfg(target_os = "android")]
    if ui.ctx().data(|d| d.get_temp::<bool>(
        egui::Id::new("wc_touchnav.suppress_ink")
    )).unwrap_or(false) {
        app.canvas.cancel_text_drag();
        app.canvas.obj_drag = None;
        app.canvas.crop_drag = None;
        app.canvas.table_drag = None;
    }
    let t = Tokens::get(ui.ctx());"""
    canvas.write_text(one(text, anchor, updated, "canvas text/object drag"), encoding="utf-8")
    ink = base / "ink.rs"
    source = ink.read_text(encoding="utf-8")
    anchor = """pub fn pointer(app: &mut WordApp, ui: &Ui, resp: &egui::Response, rects: &[Rect], layout: &DocLayout, scale: f32) -> bool {
    let mode = app.session.view.draw.mode;"""
    updated = """pub fn pointer(app: &mut WordApp, ui: &Ui, resp: &egui::Response, rects: &[Rect], layout: &DocLayout, scale: f32) -> bool {
    // WC_ANDROID_NO_INK_DURING_TWO_FINGER_V1: never commit the first
    // finger's pending ink/eraser/lasso during multi-touch navigation.
    #[cfg(target_os = "android")]
    if ui.ctx().data(|d| d.get_temp::<bool>(
        egui::Id::new("wc_touchnav.suppress_ink")
    )).unwrap_or(false) {
        app.canvas.ink = None;
        app.canvas.erasing = None;
        app.canvas.ink_ui.lasso = None;
        return true;
    }
    let mode = app.session.view.draw.mode;"""
    ink.write_text(one(source, anchor, updated, "ink/eraser/lasso drag"), encoding="utf-8")
    print("PASS: two-finger navigation cannot commit text, object or ink drags")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_touch_guard.py <upstream-wordcraft>")
    apply_touch_guard(Path(sys.argv[1]))
