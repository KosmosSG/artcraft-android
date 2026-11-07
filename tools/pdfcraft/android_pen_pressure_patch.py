#!/usr/bin/env python3
"""Android-only experimental force-responsive PDF ink annotation width.

PDFCraft v0.19 currently stores a single style.width for each PDF Ink annotation,
not per-vertex widths. This overlay uses mean Android normalized touch force to
select a per-stroke width. It deliberately does not claim within-stroke dynamics
or palm rejection; both require a deeper input / PDF appearance representation.
No desktop code changes; fail closed against upstream drift.
"""
from pathlib import Path
import sys

src = Path(sys.argv[1])

def once(rel, before, after):
    path = src / rel
    original = path.read_text()
    if "PDFCRAFT_ANDROID_INK_PRESSURE_" in original and after in original:
        return
    if original.count(before) != 1:
        raise SystemExit(f"PDFCraft stylus pressure anchor changed: {rel} {before[:70]!r} ({original.count(before)})")
    path.write_text(original.replace(before, after, 1))

once(
    "crates/ui-egui/src/tools/comments/state.rs",
    "    pub gesture: Option<Gesture>,\n",
    """    pub gesture: Option<Gesture>,
    // PDFCRAFT_ANDROID_INK_PRESSURE_STATE: a single PDF Ink annotation uses
    // one stroke width, so store mean pressure for this drawing only.
    #[cfg(target_os = "android")]
    pub(crate) android_ink_force_sum: f32,
    #[cfg(target_os = "android")]
    pub(crate) android_ink_force_samples: u32,
""",
)

path = src / "crates/ui-egui/src/tools/comments/input.rs"
original = path.read_text()
if "PDFCRAFT_ANDROID_INK_PRESSURE_CAPTURE" in original:
    raise SystemExit("Refusing to patch PDFCraft pressure overlay twice")
start = """            cv.gesture = Some(Gesture::Draw { page: cx.page, tool, points: vec![cx.to_user(o)] });
            cv.selected = None;
"""
replace = """            cv.gesture = Some(Gesture::Draw { page: cx.page, tool, points: vec![cx.to_user(o)] });
            // PDFCRAFT_ANDROID_INK_PRESSURE_RESET: no pressure from previous
            // stroke leaks into this one. Other tools remain unchanged.
            #[cfg(target_os = "android")]
            if tool == CommentTool::Ink {
                cv.android_ink_force_sum = 0.0;
                cv.android_ink_force_samples = 0;
            }
            cv.selected = None;
"""
if original.count(start) != 1:
    raise SystemExit("PDFCraft draw-start anchor changed")
original = original.replace(start, replace, 1)
target = """        if let Some(Gesture::Draw { page, tool, points }) = cv.gesture.as_mut()
            && *page == cx.page
"""
inject = """        // PDFCRAFT_ANDROID_INK_PRESSURE_CAPTURE: winit's Android stylus
        // events preserve MotionEvent.pressure as egui Touch.force. Sample
        // only during an active ink gesture and only when the OS exposes it.
        // A PDF Ink annotation supports a single width for the whole stroke.
        #[cfg(target_os = "android")]
        if tool == CommentTool::Ink && matches!(cv.gesture,
            Some(Gesture::Draw { page, tool: CommentTool::Ink, .. }) if page == cx.page)
        {
            let force = ui.input(|i| i.events.iter().rev().find_map(|event| {
                match event {
                    egui::Event::Touch { force: Some(force), .. } if force.is_finite()
                        => Some((*force).clamp(0.0, 1.0)),
                    _ => None,
                }
            }));
            if let Some(force) = force {
                cv.android_ink_force_sum += force;
                cv.android_ink_force_samples = cv.android_ink_force_samples.saturating_add(1);
            }
        }
        if let Some(Gesture::Draw { page, tool, points }) = cv.gesture.as_mut()
            && *page == cx.page
"""
if original.count(target) != 1:
    raise SystemExit("PDFCraft draw force sampling anchor changed")
original = original.replace(target, inject, 1)
target = """                cv.settle(now, page, tool, &points);
                view.pending_edit = Some(new_comment(cx, tool, shape, String::new()));
"""
replace = """                cv.settle(now, page, tool, &points);
                let mut edit = new_comment(cx, tool, shape, String::new());
                // PDFCRAFT_ANDROID_INK_PRESSURE_COMMIT: preserve the standard
                // undoable PDF Ink annotation with a pressure-scaled width.
                // No fake intra-stroke variable width is written to the PDF.
                #[cfg(target_os = "android")]
                if tool == CommentTool::Ink && cv.android_ink_force_samples > 0 {
                    if let Edit::AddAnnotation(annotation) = &mut edit {
                        let pressure = (cv.android_ink_force_sum
                            / cv.android_ink_force_samples as f32).clamp(0.0, 1.0);
                        annotation.style.width =
                            (annotation.style.width * (0.4 + f64::from(pressure) * 1.6))
                                .clamp(0.25, 75.0);
                    }
                }
                view.pending_edit = Some(edit);
"""
if original.count(target) != 1:
    raise SystemExit("PDFCraft ink commit anchor changed")
original = original.replace(target, replace, 1)
path.write_text(original)
print("PASS: Android ink pressure samples mapped to bounded per-stroke PDF Ink style width; no desktop change")
