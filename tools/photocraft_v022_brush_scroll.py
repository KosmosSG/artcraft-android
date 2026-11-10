#!/usr/bin/env python3
"""Guard two-finger trackpad scrolling over PhotoCraft's brush preset lists.

Apply only in the disposable ARM64 CI checkout, after the already-working
Android.1 trackpad overlay. Do not intercept stylus or touchscreen events.
The native trackpad gestures feed the hovered brush ScrollArea; canvas
pan/pinch stays unchanged outside that area.
"""
import argparse
from pathlib import Path
import subprocess

UPSTREAM_SHA = "5000240c6e5dc30a024d20f97a620c78eca10d1e"
BRUSHES_SHA = "9633125d791a59259225fb99e1f71c0c8941ec3b"


def replace_once(path: Path, before: str, after: str) -> None:
    data = path.read_text(encoding="utf-8")
    count = data.count(before)
    if count != 1:
        raise RuntimeError(f"Unreviewed PhotoCraft brush scroll anchor: {path}: {count} matches")
    path.write_text(data.replace(before, after, 1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    a = parser.parse_args()
    head = subprocess.check_output(["git", "-C", str(a.upstream), "rev-parse", "HEAD"], text=True).strip()
    if head != UPSTREAM_SHA:
        raise RuntimeError(f"Refusing unreviewed official PhotoCraft upstream commit: {head}")

    brushes = a.upstream / "crates/ui-egui/src/panels/brushes_tab.rs"
    sha = subprocess.check_output(["git", "-C", str(a.upstream), "hash-object",
                                   "crates/ui-egui/src/panels/brushes_tab.rs"], text=True).strip()
    if sha != BRUSHES_SHA:
        raise RuntimeError(f"Refusing unreviewed brush list implementation: {sha}")

    # The same ScrollArea is used for both the floating Brush Preset picker
    # and Window > Brushes. Keep viewport rectangles for only the last pass.
    replace_once(
        brushes,
        "    egui::ScrollArea::vertical().id_salt(layout.id).max_height(layout.max_height).auto_shrink([false, true]).show(ui, |ui| {",
        "    let brush_scroll = egui::ScrollArea::vertical().id_salt(layout.id).max_height(layout.max_height).auto_shrink([false, true]).show(ui, |ui| {"
    )
    replace_once(
        brushes,
        "    // The dragged preset or group follows the pointer.",
        """    #[cfg(target_os = "android")]
    {
        let ctx = ui.ctx();
        let pass = ctx.cumulative_pass_nr();
        let key = egui::Id::new("pc-trackpad-brush-scroll-areas");
        let (seen, mut rects) = ctx.data(|d|
            d.get_temp::<(u64, Vec<egui::Rect>)>(key).unwrap_or((pass, Vec::new())));
        if seen != pass {
            rects.clear();
        }
        rects.push(brush_scroll.inner_rect);
        ctx.data_mut(|d| d.insert_temp(key, (pass, rects)));
    }
    // The dragged preset or group follows the pointer."""
    )
    with brushes.open("a", encoding="utf-8") as f:
        f.write("""
/// The last visible Brush Preset picker / Brushes tab scroll viewports.
/// Read during the next Android input pass; do not treat the entire canvas
/// or unrelated popup menus as the brush library.
#[cfg(target_os = "android")]
pub fn artcraft_brush_scroll_area(ctx: &egui::Context, point: egui::Pos2) -> bool {
    let pass = ctx.cumulative_pass_nr();
    ctx.data(|d| {
        d.get_temp::<(u64, Vec<egui::Rect>)>(
            egui::Id::new("pc-trackpad-brush-scroll-areas")
        ).is_some_and(|(seen, rects)| {
            seen.saturating_add(1) >= pass && rects.iter().any(|r| r.contains(point))
        })
    })
}
""")

    wheel = a.adapter / "src/trackpad_wheel.rs"
    before = """    let mut native_canvas = false;
    if menu.is_none() {
        for [dx, dy, scale, x, y] in native {
            let at = Pos2::new(rect.left() + x / ppp, rect.top() + y / ppp);
            let fallback = ctx.pointer_hover_pos().unwrap_or(rect.center());
            let pos = if rect.contains(at) { at } else { fallback };
            native_canvas |= gestures.trackpad_view(rect, pos, Vec2::new(dx / ppp, dy / ppp), scale);
        }
    }"""
    after = """    let mut native_canvas = false;
    // Native API 34+ trackpad scroll axes are already pixels. Never route
    // those events into canvas panning when a brush scroll viewport is hit.
    let mut native_brush: Vec<(Pos2, Vec2)> = Vec::new();
    if menu.is_none() {
        for [dx, dy, scale, x, y] in native {
            let at = Pos2::new(rect.left() + x / ppp, rect.top() + y / ppp);
            // Some physical touchpads report an origin instead of the cursor
            // position in gesture samples; favour the actual hovered brush list.
            let hover = raw.events.iter().rev().find_map(|event| match event {
                Event::PointerMoved(p) => Some(*p), _ => None,
            }).or_else(|| ctx.pointer_hover_pos());
            let pos = match hover {
                Some(p) if photocraft_ui_egui::brushes_tab::artcraft_brush_scroll_area(ctx, p) => p,
                _ if rect.contains(at) => at,
                Some(p) => p,
                None => rect.center(),
            };
            let scroll = Vec2::new(dx / ppp, dy / ppp);
            if photocraft_ui_egui::brushes_tab::artcraft_brush_scroll_area(ctx, pos) {
                if scroll.length_sq() > 0.0001 {
                    native_brush.push((pos, scroll));
                }
                // A pinch over the Brush Library must not zoom the canvas.
            } else {
                native_canvas |= gestures.trackpad_view(rect, pos, scroll, scale);
            }
        }
    }
    // Inject only when winit has not already delivered the same wheel.
    // Preserve the native event's sign, both axes, and pixel-to-point ratio.
    if !native_wheel_present && menu.is_none() {
        for (pos, delta) in native_brush {
            raw.events.push(Event::PointerMoved(pos));
            raw.events.push(Event::MouseWheel {
                unit: MouseWheelUnit::Point, delta, phase: TouchPhase::Move,
                modifiers: egui::Modifiers::NONE, source: MouseWheelSource::Trackpad,
            });
        }
    }"""
    replace_once(wheel, before, after)

    # Java touchpad pinch bridge must not change the canvas underneath a
    # hovered brush library. Touchscreen/stylus paths are not modified.
    replace_once(
        wheel,
        "        let _ = gestures.trackpad_view(rect, pos, Vec2::ZERO, scale);",
        """        if !photocraft_ui_egui::brushes_tab::artcraft_brush_scroll_area(ctx, pos) {
            let _ = gestures.trackpad_view(rect, pos, Vec2::ZERO, scale);
        }"""
    )
    replace_once(
        wheel,
        "            if menu.is_none() && !modifiers.any()",
        """            if menu.is_none()
                && !photocraft_ui_egui::brushes_tab::artcraft_brush_scroll_area(ctx, pointer)
                && !modifiers.any()"""
    )

    assert "native_brush.push((pos, scroll))" in wheel.read_text()
    assert "brush_scroll.inner_rect" in brushes.read_text()
    assert wheel.read_text().count("artcraft_brush_scroll_area") == 3
    assert "pub(crate) fn trackpad_view" in (a.adapter / "src/canvas_gesture.rs").read_text()
    print("PASS: brush preset ScrollArea uses scoped two-finger trackpad wheel routing.")
    print("PASS: outside-brush canvas pan/pinch and native/Java deduplication preserved.")
    print("NOTE: brush scrolling behavior remains unverified on HONOR MagicPad 4 until device testing.")


if __name__ == "__main__":
    main()
