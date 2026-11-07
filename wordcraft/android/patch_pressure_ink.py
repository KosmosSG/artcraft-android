#!/usr/bin/env python3
"""Pressure-sensitive ink, Android-only overlay after smooth stylus patch.

The upstream WordCraft document format stores one width per ink object.
Store at most 12 short, standard-width, continuous freeform objects for one
pressure stroke, grouped into one undo step; no custom DOCX data is required.
Desktop checkout, published release and production signing are untouched.
"""
from pathlib import Path


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"WordCraft pressure integration: {label} anchor found {count} times")
    return text.replace(old, new, 1)


def apply_pressure_ink(source_root: Path, pressure_module: Path) -> None:
    ink = source_root / "crates" / "ui-egui" / "src" / "ink.rs"
    code = ink.read_text(encoding="utf-8")
    assert "WC_ANDROID_PRESSURE_STROKES_V1" in pressure_module.read_text(encoding="utf-8")
    code = one(
        code,
        '#[cfg(target_os = "android")]\ninclude!("wordcraft-stylus-smoothing.rs.inc");',
        '#[cfg(target_os = "android")]\ninclude!("wordcraft-stylus-smoothing.rs.inc");\n'
        '#[cfg(target_os = "android")]\ninclude!("wordcraft-stylus-pressure.rs.inc");',
        "pressure-width helper module",
    )
    code = one(
        code,
        """pub struct InkDrag {
    page: usize,
    tool: InkTool,
    pts: Vec<[f32; 2]>,
}""",
        """pub struct InkDrag {
    page: usize,
    tool: InkTool,
    pts: Vec<[f32; 2]>,
    #[cfg(target_os = "android")]
    pressure: Vec<f32>,
    #[cfg(target_os = "android")]
    pressure_on: bool,
}""",
        "align native pressure to saved ink positions",
    )
    code = one(code, 'data.remove_temp::<Vec<[f32; 2]>>(', 'data.remove_temp::<Vec<[f32; 3]>>(', "native point pressure batch")
    code = one(code, 'let batch: Vec<[f32; 2]> = Vec::new();', 'let batch: Vec<[f32; 3]> = Vec::new();', "desktop default batch")
    code = one(
        code,
        """            let had_batch = !batch.is_empty();
            if starts {
                // Seed from the actual earliest stylus sample if available,
                // rather than the last pointer position in the frame.
                let first = batch.first().and_then(|[x, y]|
                    page_at(rects, layout, scale, pos2(*x, *y))
                ).or_else(|| at.and_then(|p| page_at(rects, layout, scale, p)));
                if let Some((page, x, y)) = first {
                    app.canvas.ink = Some(InkDrag { page, tool, pts: vec![[x, y]] });
                }
            }""",
        """            let had_batch = !batch.is_empty();
            #[cfg(target_os = "android")]
            let pressure_requested = ui.ctx().data(|d| d.get_temp::<bool>(
                egui::Id::new("wc_stylus.pressure_enabled")
            )).unwrap_or(false);
            if starts {
                let first = batch.first().and_then(|[x, y, pressure]|
                    page_at(rects, layout, scale, pos2(*x, *y))
                        .map(|(page, x, y)| (page, x, y, *pressure))
                ).or_else(|| at.and_then(|p| page_at(rects, layout, scale, p))
                    .map(|(page, x, y)| (page, x, y, 0.0)));
                if let Some((page, x, y, pressure)) = first {
                    app.canvas.ink = Some(InkDrag {
                        page, tool, pts: vec![[x, y]],
                        #[cfg(target_os = "android")]
                        pressure: vec![pressure],
                        #[cfg(target_os = "android")]
                        pressure_on: pressure_requested && had_batch
                            && tool != InkTool::Highlighter,
                    });
                }
            }""",
        "pressure captured only for real stylus contact",
    )
    code = one(
        code,
        """                for [sx, sy] in batch {
                    if let Some((x, y)) = on_page(rects, layout, scale, d.page, pos2(sx, sy)) {
                        let far = d.pts.last().is_none_or(|[lx, ly]|
                            ((x - lx).powi(2) + (y - ly).powi(2)).sqrt() * scale >= MIN_STEP_PX
                        );
                        if far && d.pts.len() < MAX_POINTS { d.pts.push([x, y]); }
                    }
                }""",
        """                for [sx, sy, pressure] in batch {
                    if let Some((x, y)) = on_page(rects, layout, scale, d.page, pos2(sx, sy)) {
                        let far = d.pts.last().is_none_or(|[lx, ly]|
                            ((x - lx).powi(2) + (y - ly).powi(2)).sqrt() * scale >= MIN_STEP_PX
                        );
                        if far && d.pts.len() < MAX_POINTS {
                            d.pts.push([x, y]);
                            #[cfg(target_os = "android")]
                            d.pressure.push(pressure);
                        }
                    }
                }""",
        "preserve every sampled pressure alongside its point",
    )
    code = one(
        code,
        '                if far && d.pts.len() < MAX_POINTS { d.pts.push([x, y]); }\n            }\n            if released',
        '                if far && d.pts.len() < MAX_POINTS {\n'
        '                    d.pts.push([x, y]);\n'
        '                    #[cfg(target_os = "android")]\n'
        '                    d.pressure.push(0.0);\n'
        '                }\n'
        '            }\n            if released',
        "preserve point/pressure alignment on sparse devices",
    )
    code = one(
        code,
        """            if released && let Some(d) = app.canvas.ink.take() {
                #[cfg(target_os = "android")]
                let points = wc_smooth_stroke(&d.pts, MAX_POINTS);
                #[cfg(not(target_os = "android"))]
                let points = d.pts;
                let _ = app.run("draw.stroke", json!({"page": d.page, "points": points, "tool": d.tool.name()}));
            }""",
        """            if released && let Some(d) = app.canvas.ink.take() {
                #[cfg(target_os = "android")]
                let points = wc_smooth_stroke(&d.pts, MAX_POINTS);
                #[cfg(not(target_os = "android"))]
                let points = d.pts;
                #[cfg(target_os = "android")]
                let pressure = wc_smooth_pressures(&d.pressure, MAX_POINTS);
                #[cfg(target_os = "android")]
                let dynamic = d.pressure_on
                    && pressure.len() == points.len()
                    && pressure.iter().any(|p| *p > 0.0);
                #[cfg(not(target_os = "android"))]
                let dynamic = false;
                #[cfg(target_os = "android")]
                if dynamic {
                    let base = app.session.view.draw.settings(d.tool).width;
                    let parts = wc_pressure_segments(&points, &pressure, base, 12);
                    if parts.is_empty() {
                        let _ = app.run("draw.stroke", json!({
                            "page": d.page, "points": points, "tool": d.tool.name()
                        }));
                    } else {
                        // Separate short freeforms preserve width in DOCX. Keep
                        // one undo step and prevent Ink-to-Shape auto conversion.
                        let auto_shape = app.session.view.draw.ink_to_shape;
                        app.session.view.draw.ink_to_shape = false;
                        for (index, (path, width)) in parts.into_iter().enumerate() {
                            if index > 0 { app.session.join_next_undo(); }
                            if let Err(err) = app.run("draw.stroke", json!({
                                "page": d.page, "points": path, "tool": d.tool.name(),
                                "width": width
                            })) {
                                log::warn!("WordCraft pressure stroke segment rejected: {err}");
                                break;
                            }
                        }
                        app.session.view.draw.ink_to_shape = auto_shape;
                    }
                } else {
                    let _ = app.run("draw.stroke", json!({
                        "page": d.page, "points": points, "tool": d.tool.name()
                    }));
                }
            }""",
        "persist pressure widths as bounded standard freeforms",
    )
    code = one(
        code,
        """    let width = (set.width * s).max(1.0);
    if let [only] = pts.as_slice() {
        painter.circle_filled(*only, width / 2.0, color);
    } else {
        painter.add(egui::Shape::line(pts, Stroke::new(width, color)));
    }""",
        """    let width = (set.width * s).max(1.0);
    #[cfg(target_os = "android")]
    let variable = d.pressure_on && d.pressure.len() == d.pts.len();
    #[cfg(target_os = "android")]
    let sample_pressures = wc_smooth_pressures(&d.pressure, MAX_POINTS);
    #[cfg(target_os = "android")]
    if variable && sample_pressures.len() == pts.len()
        && sample_pressures.iter().any(|p| *p > 0.0)
    {
        for (pair, p) in pts.windows(2).zip(sample_pressures.windows(2)) {
            let thickness = wc_pressure_width(width, (p[0] + p[1]) * 0.5).max(1.0);
            painter.line_segment([pair[0], pair[1]], Stroke::new(thickness, color));
            painter.circle_filled(pair[1], thickness * 0.5, color);
        }
        return;
    }
    if let [only] = pts.as_slice() {
        painter.circle_filled(*only, width / 2.0, color);
    } else {
        painter.add(egui::Shape::line(pts, Stroke::new(width, color)));
    }""",
        "live stroke changes width according to pressure samples",
    )
    (ink.parent / "wordcraft-stylus-pressure.rs.inc").write_text(
        pressure_module.read_text(encoding="utf-8"), encoding="utf-8"
    )
    ink.write_text(code, encoding="utf-8")
    print("PASS: optional dynamic ink widths, 12-segment maximum, standard DOCX shapes")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_pressure_ink.py <upstream-wordcraft> <stylus_pressure.rs.inc>")
    apply_pressure_ink(Path(sys.argv[1]), Path(sys.argv[2]))
