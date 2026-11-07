#!/usr/bin/env python3
"""Android-only stylus ink smoothing, historical points and hover overlay.

Applied ONLY to the pinned WordCraft source checkout inside disposable CI.
Desktop upstream and all published release tags remain untouched.
"""
from pathlib import Path


def one(source: str, before: str, after: str, name: str) -> str:
    n = source.count(before)
    if n != 1:
        raise RuntimeError(f"WordCraft stylus ink integration: {name}: found {n} anchors, need one")
    return source.replace(before, after, 1)


def apply_stylus_ink(wordcraft_root: Path, curve_file: Path) -> None:
    ink = wordcraft_root / "crates" / "ui-egui" / "src" / "ink.rs"
    source = ink.read_text(encoding="utf-8")
    assert "WC_STYLUS_CURVE_SMOOTHING_V1" in curve_file.read_text(encoding="utf-8")
    source = one(
        source,
        "use crate::WordApp;\n",
        'use crate::WordApp;\n#[cfg(target_os = "android")]\ninclude!("wordcraft-stylus-smoothing.rs.inc");\n',
        "source module include",
    )
    old_pen = """            if starts && let Some((page, x, y)) = at.and_then(|p| page_at(rects, layout, scale, p)) {
                app.canvas.ink = Some(InkDrag { page, tool, pts: vec![[x, y]] });
            } else if down
                && let Some(p) = at
                && let Some(d) = app.canvas.ink.as_mut()
                && let Some((x, y)) = on_page(rects, layout, scale, d.page, p)
            {
                let far = d.pts.last().is_none_or(|[lx, ly]| ((x - lx).powi(2) + (y - ly).powi(2)).sqrt() * scale >= MIN_STEP_PX);
                if far && d.pts.len() < MAX_POINTS {
                    d.pts.push([x, y]);
                }
            }
            if released && let Some(d) = app.canvas.ink.take() {
                let _ = app.run("draw.stroke", json!({"page": d.page, "points": d.pts, "tool": d.tool.name()}));
            }"""
    new_pen = """            #[cfg(target_os = "android")]
            let batch = ui.ctx().data_mut(|data| data.remove_temp::<Vec<[f32; 2]>>(
                egui::Id::new("wc_stylus.path_samples")
            )).unwrap_or_default();
            #[cfg(not(target_os = "android"))]
            let batch: Vec<[f32; 2]> = Vec::new();
            let had_batch = !batch.is_empty();
            if starts {
                // Seed from the actual earliest stylus sample if available,
                // rather than the last pointer position in the frame.
                let first = batch.first().and_then(|[x, y]|
                    page_at(rects, layout, scale, pos2(*x, *y))
                ).or_else(|| at.and_then(|p| page_at(rects, layout, scale, p)));
                if let Some((page, x, y)) = first {
                    app.canvas.ink = Some(InkDrag { page, tool, pts: vec![[x, y]] });
                }
            }
            if (down || released) && let Some(d) = app.canvas.ink.as_mut() {
                for [sx, sy] in batch {
                    if let Some((x, y)) = on_page(rects, layout, scale, d.page, pos2(sx, sy)) {
                        let far = d.pts.last().is_none_or(|[lx, ly]|
                            ((x - lx).powi(2) + (y - ly).powi(2)).sqrt() * scale >= MIN_STEP_PX
                        );
                        if far && d.pts.len() < MAX_POINTS { d.pts.push([x, y]); }
                    }
                }
            }
            // Retain original mouse/finger drawing behavior and single-sample
            // devices when native history is absent.
            if !had_batch && down
                && let Some(p) = at
                && let Some(d) = app.canvas.ink.as_mut()
                && let Some((x, y)) = on_page(rects, layout, scale, d.page, p)
            {
                let far = d.pts.last().is_none_or(|[lx, ly]| ((x - lx).powi(2) + (y - ly).powi(2)).sqrt() * scale >= MIN_STEP_PX);
                if far && d.pts.len() < MAX_POINTS { d.pts.push([x, y]); }
            }
            if released && let Some(d) = app.canvas.ink.take() {
                #[cfg(target_os = "android")]
                let points = wc_smooth_stroke(&d.pts, MAX_POINTS);
                #[cfg(not(target_os = "android"))]
                let points = d.pts;
                let _ = app.run("draw.stroke", json!({"page": d.page, "points": points, "tool": d.tool.name()}));
            }"""
    source = one(source, old_pen, new_pen, "bounded historical pen trajectory")
    source = one(
        source,
        "    let pts: Vec<Pos2> = d.pts.iter().map(|p| map(*p)).collect();",
        """    #[cfg(target_os = "android")]
    let preview = wc_smooth_stroke(&d.pts, MAX_POINTS);
    #[cfg(not(target_os = "android"))]
    let preview = d.pts.clone();
    let pts: Vec<Pos2> = preview.iter().map(|p| map(*p)).collect();""",
        "live preview and document trajectory match",
    )
    source = one(
        source,
        "    paint_lasso(app, painter, rects, layout, scale);\n",
        """    paint_lasso(app, painter, rects, layout, scale);
    // WC_ANDROID_STYLUS_HOVER_CURSOR_V1: render a noncontact cursor only
    // over a document page, never on the ribbon or popup menus. Hover creates
    // no ink, does not steal pointer focus, and survives a stationary pen.
    #[cfg(target_os = "android")]
    if let Some([hx, hy]) = painter.ctx().data(|data| data.get_temp::<[f32; 2]>(
        egui::Id::new("wc_stylus.hover_pos")
    )) {
        let at = pos2(hx, hy);
        if rects.iter().any(|rect| rect.contains(at)) {
            let radius = match app.session.view.draw.mode {
                DrawMode::Pen(tool) => (app.session.view.draw.settings(tool).width * scale / 2.0).clamp(4.0, 18.0),
                DrawMode::Eraser => 10.0,
                _ => 0.0,
            };
            if radius > 0.0 {
                painter.circle_stroke(at, radius, Stroke::new(1.5, Color32::from_rgb(37, 118, 222)));
            }
        }
    }
""",
        "canvas-only non-contact pen hover cursor",
    )
    source = one(
        source,
        "const MIN_STEP_PX: f32 = 1.5;",
        """#[cfg(target_os = "android")]
const MIN_STEP_PX: f32 = 0.8;
#[cfg(not(target_os = "android"))]
const MIN_STEP_PX: f32 = 1.5;""",
        "higher resolution Android pen sampling only",
    )
    (ink.parent / "wordcraft-stylus-smoothing.rs.inc").write_text(
        curve_file.read_text(encoding="utf-8"), encoding="utf-8"
    )
    ink.write_text(source, encoding="utf-8")
    print("PASS: isolated Android stylus high-rate samples, smooth preview/save, non-contact hover cursor")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_stylus_ink.py <upstream-wordcraft> <stylus_curve.rs.inc>")
    apply_stylus_ink(Path(sys.argv[1]), Path(sys.argv[2]))
