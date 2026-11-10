"""VectorCraft Android.5: first-trackpad-pinch canvas anchor and menu-only natural scroll.

Narrow overlay applied after the proven Android.4 adapter and official v0.23.0
canvas input patches. Do not touch native gesture classification or quit flow.
Fail closed on any generated source drift, before the expensive ARM64 build.
"""
from pathlib import Path


def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Android.5 {label} anchor count={count}; refusing generated source change")
    return source.replace(old, new, 1)


def patch(root: Path) -> None:
    canvas = root / "source/vectorcraft/crates/ui-egui/src/canvas/input.rs"
    source = canvas.read_text()
    source = once(
        source,
        """    let gesture_on_canvas = touch_center.is_some();
    // Zoom around the pointer, and scroll""",
        """    let gesture_on_canvas = touch_center.is_some();
    // MagicOS may deliver native trackpad Event::Zoom BEFORE any mouse hover
    // location or first two-finger scroll. The working touchscreen gesture
    // already has a center; for a hoverless trackpad pinch use the canvas
    // center ONLY when a document is open and no menu/dialog is intercepting.
    // Never use this fallback for touchscreen multitouch, mouse-wheel zoom,
    // out-of-canvas hover, or object selection.
    let trackpad_pinch_needs_anchor = pointer.hover_pos().is_none()
        && !egui::Popup::is_any_open(ui.ctx())
        && app.ui.dialog.is_none()
        && !app.ui.palette_open
        && app.session.active().is_some()
        && ui.input(|i| {
            i.multi_touch().is_none()
                && i.events.iter().any(|event| matches!(event,
                    egui::Event::Zoom(scale)
                    if scale.is_finite() && (*scale - 1.0).abs() > 1e-6))
        });
    // Zoom around the pointer, and scroll""",
        "first pinch eligible hoverless anchor",
    )
    source = once(
        source,
        """    if resp.hovered() || gesture_on_canvas {
        if (factor - 1.0).abs() > 1e-6
            && let (Some(p), Some(vm)) = (touch_center.or(hover), app.view_mut())
        {
            zoom_about(vm, rect, p, vm.zoom * factor);
        }
        if scroll != egui::Vec2::ZERO {
            scroll_view(app, ui, scroll);
        }
        if let Some(p) = hover""",
        """    if resp.hovered() || gesture_on_canvas || trackpad_pinch_needs_anchor {
        if (factor - 1.0).abs() > 1e-6
            && let (Some(p), Some(vm)) = (
                touch_center.or(hover).or_else(|| trackpad_pinch_needs_anchor.then_some(rect.center())),
                app.view_mut())
        {
            zoom_about(vm, rect, p, vm.zoom * factor);
        }
        // The hoverless exception is ZOOM-ONLY: never send a missing-hover
        // trackpad pan into the canvas or accidentally select artwork.
        if (resp.hovered() || gesture_on_canvas) && scroll != egui::Vec2::ZERO {
            scroll_view(app, ui, scroll);
        }
        if let Some(p) = hover""",
        "canvas zoom gate",
    )
    canvas.write_text(source)

    # AXIS_GESTURE_SCROLL_Y_DISTANCE is a viewport scroll distance; egui
    # MouseWheel::delta is content motion. Reverse vertical *popup* wheel
    # steps to make fingers UP reveal later items; fingers DOWN earlier ones.
    # Keep horizontal deltas, desktop mouse wheel, pinch and canvas unchanged.
    # Android.23 PhotoCraft parity intentionally keeps the original egui-winit
    # source as Unknown: do not reinstall the removed global classifier.
    adapter = root / "adapters/vectorcraft/src/lib.rs"
    rust = adapter.read_text()
    rust = once(
        rust,
        """        // PhotoCraft parity: do NOT rewrite Android native wheel sources
        // into Trackpad. Let egui-winit deliver original wheel phase/delta;
        // this avoids competing inertial scroll paths on MagicOS.
        // Trigger high-refresh redraws only during actual gestures""",
        """        // PhotoCraft parity: do NOT rewrite Android native wheel sources
        // into Trackpad. Let egui-winit deliver original wheel phase/delta;
        // this avoids competing inertial scroll paths on MagicOS.
        // Android.5 natural vertical menu navigation for MagicOS trackpad.
        // AXIS_GESTURE_SCROLL_Y_DISTANCE is viewport motion; egui expects
        // content motion, so reverse only vertical PixelDelta while popup open.
        // No mouse-wheel lines/pages, canvas, pinch or touchscreen touch event.
        if egui::Popup::is_any_open(ctx)
            && !raw.events.iter().any(|event| matches!(event, egui::Event::Touch { .. }))
        {
            for event in &mut raw.events {
                if let egui::Event::MouseWheel {
                    unit: egui::MouseWheelUnit::Point,
                    source: egui::MouseWheelSource::Trackpad | egui::MouseWheelSource::Unknown,
                    delta, ..
                } = event {
                    delta.y = -delta.y;
                }
            }
        }
        // Trigger high-refresh redraws only during actual gestures""",
        "menu-only natural vertical trackpad scroll",
    )
    adapter.write_text(rust)
    assert "self.menu_scroll.apply(ctx, raw);" not in rust, "double popup scroll integrator"
    assert "trackpad_pinch_needs_anchor" in source
    assert "gesture_on_canvas" in source
    assert "vc_quit_after_native" in rust, "preserve proven native-loop-first Ctrl+Q"
    print("PASS: Android.5 hoverless first pinch fallback, natural menu trackpad direction, quit unchanged")


if __name__ == "__main__":
    import sys
    patch(Path(sys.argv[1]))
