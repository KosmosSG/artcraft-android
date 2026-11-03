#!/usr/bin/env python3
"""GridCraft v0.15 Android: allow touch/trackpad range selection without losing swipe scrolling.

Pure source transformation of an isolated exact v0.15 upstream checkout.
A quick swipe still pans, ordinary mouse primary-drag selects, touch may hold
before dragging to extend a selection, and touching the fill handle drags/fills.
A Gc Tools toggle enables direct single-finger drag selection on demand.
"""
from pathlib import Path
import argparse
import json
import tomllib

VERSION = "0.15.0"
SHOW = "crates/ui-egui/src/grid/show.rs"
INTERACT = "crates/ui-egui/src/grid/interact.rs"
MARKER = "GRIDCRAFT_ANDROID_TOUCH_SELECT_V1"


def once(source, needle, replacement, name):
    n = source.count(needle)
    if n != 1:
        raise RuntimeError(f"{name}: expected unique upstream v0.15 anchor, saw {n}: {needle[:85]!r}")
    return source.replace(needle, replacement, 1)


def port(root: Path, verify_only=False):
    root = root.resolve()
    manifest = root / "Cargo.toml"
    if not manifest.exists() or tomllib.loads(manifest.read_text())["workspace"]["package"]["version"] != VERSION:
        raise RuntimeError("Touch selection port only applies to separate official GridCraft 0.15 checkout")
    show_path, interact_path = root / SHOW, root / INTERACT
    show, interact = show_path.read_text(), interact_path.read_text()
    if MARKER in show or MARKER in interact:
        raise RuntimeError("Android touch-selection port already applied")
    touch_pan_old = """    // A one-finger touch drag pans the sheet, the content following the finger; it doesn't select.
    // (Two fingers pinch-zoom through `zoom_delta` above.)
    if resp.drag_started() && ui.input(|i| i.any_touches()) {
        app.grid.touch_pan = true;
    }"""
    touch_pan_new = """    // GRIDCRAFT_ANDROID_TOUCH_SELECT_V1:
    // Preserve quick one-finger swipes for scroll, and two-finger zoom.
    // A long-press then drag selects a range; a drag from the fill handle
    // fills/extends cells; a physical mouse/trackpad primary-button drag
    // uses GridCraft's unchanged Drag::Select path.
    // An explicit Gc Tools toggle offers direct touch drag-selection.
    if resp.drag_started() && ui.input(|i| i.any_touches()) {
        let gesture = ui.input(|i| {
            (i.pointer.press_origin(), i.pointer.press_start_time(), i.time, i.multi_touch().is_some())
        });
        let (press, start_at, now, multi_touch) = gesture;
        let select_mode = ui.ctx().data(|d| {
            d.get_temp::<bool>(egui::Id::new("gridcraft.android.touch_select"))
        }).unwrap_or(false);
        let long_hold = start_at.is_some_and(|start| now - start >= 0.40);
        let touch_geo = make_geo(app, view.scroll);
        let end = touch_geo.range_rect(sh, sel.current()).right_bottom();
        // The visible 9px fill square is too small for a fingertip; its touch
        // hit target is wider, but ONLY inside the pane showing the handle.
        let on_fill_handle = press.is_some_and(|p| {
            let logical = touch_geo.mirror_pos(p);
            (logical - end).length() <= 22.0
                && touch_geo.range_panes(RangeRef::cell(sel.current().end))
                    .iter().any(|pane| pane.contains(logical))
        });
        app.grid.touch_pan = multi_touch || !(select_mode || long_hold || on_fill_handle);
    }"""
    show = once(show, touch_pan_old, touch_pan_new, SHOW)
    touch_handle_old = "    let handle = Rect::from_center_size(cur_rect.right_bottom(), vec2(9.0, 9.0));"
    touch_handle_new = """    // GRIDCRAFT_ANDROID_TOUCH_SELECT_V1: fingertip-sized hit target only
    // on true touchscreen input; mouse hit testing stays pixel precise.
    let handle_size = if ctx.input(|i| i.any_touches()) { 44.0 } else { 9.0 };
    let handle = Rect::from_center_size(cur_rect.right_bottom(), vec2(handle_size, handle_size));"""
    interact = once(interact, touch_handle_old, touch_handle_new, INTERACT)
    # The source's show_grid_interactions already skips *only* touch_pan.
    # All drag select, drag fill, shift+arrow, popup and scroll math stay intact.
    for label, source, must in [
        (SHOW, show, ["long_hold", "app.grid.touch_pan = multi_touch ||", "on_fill_handle", "gridcraft.android.touch_select"]),
        (INTERACT, interact, ["let handle_size =", "Drag::Select", "Drag::Fill"]),
    ]:
        for token in must:
            if token not in source:
                raise RuntimeError(f"{label}: missing expected guarded behavior: {token}")
    if not verify_only:
        show_path.write_text(show)
        interact_path.write_text(interact)
    return {
        "upstream": VERSION,
        "touch_hold_and_drag_select": True,
        "touch_fill_handle_hit_area": 44,
        "mouse_drag_selection_preserved": True,
        "single_touch_swipe_pan_preserved": True,
        "two_finger_zoom_preserved": True,
        "source_modified": not verify_only,
        "compiled_or_tested_on_device": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream_checkout", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    opts = parser.parse_args()
    print(json.dumps(port(opts.upstream_checkout, opts.verify_only), indent=2))
