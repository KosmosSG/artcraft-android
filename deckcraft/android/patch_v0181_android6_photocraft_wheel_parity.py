#!/usr/bin/env python3
"""DeckCraft Android.6 TEST ONLY: mirror verified PhotoCraft radial-wheel UX.

Applied after the approved Android.5 launcher-glyph sizing patch, inside the
disposable Actions builder. Keep original launcher Dk glyph, red round hub,
DeckCraft native white icons, keyboard/DCS/PPTX/font/updater code unchanged.
PhotoCraft reference: tools/photocraft_v022_stylus_wheel.rs on the published
v0.23.1 Android.5 optimized source branch.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_v0181_android6_photocraft_wheel_parity.py <builder>")
root = Path(sys.argv[1])
wheel = root / "source/deckcraft/crates/ui-egui/src/android_wheel.rs"
logo = root / "source/deckcraft/crates/ui-egui/src/android_wheel_logo.rgba"
if not wheel.is_file() or not logo.is_file():
    raise RuntimeError("DeckCraft Android.5 branded wheel is required")
text = wheel.read_text(encoding="utf-8")

def one(before, after):
    global text
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"Unsafe DeckCraft wheel anchor {count}x: {before[:110]!r}")
    text = text.replace(before, after, 1)

# Match PhotoCraft default settings for fresh installs and Restore Default,
# without destroying the user's prior persisted wheel settings.
one("const SIZE: f32 = 304.0;", "const SIZE: f32 = 312.0;")
one("const DEFAULT_SIZE: f32 = 75.0;", "const DEFAULT_SIZE: f32 = 100.0;")
one("const DEFAULT: [usize; 8] = [0, 1, 2, 3, 4, 5, 6, 7];",
    "const DEFAULT: [usize; 8] = [2, 3, 4, 1, 7, 0, 6, 5];")
one("use crate::SlideApp;", "use crate::SlideApp;\nuse std::time::{Duration,Instant};\n"
    "const FEEDBACK_HOLD: Duration = Duration::from_millis(1900);\n"
    "const FEEDBACK_FADE: Duration = Duration::from_millis(500);")
one("    signal_seen: u8,\n}", """    signal_seen: u8,
    // Noninteractive PhotoCraft-style bottom-center feedback pill.
    message: &'static str,
    message_at: Instant,
}""")
one("            pending: None, signal_seen: 0,",
    """            pending: None, signal_seen: 0,
            message: "Hover + single-press: open wheel",
            message_at: Instant::now(),""")
one("    fn scale(&self) -> f32 { self.size / 100.0 }",
    """    fn scale(&self) -> f32 { self.size / 100.0 }
    fn notify(&mut self, message: &'static str) {
        self.message = message;
        self.message_at = Instant::now();
    }""")
one("    w.hover_isolated = false;\n    w.save();",
    """    w.hover_isolated = false;
    w.notify(if w.enabled { "Wheel ON • hover + single press" } else { "Wheel OFF" });
    w.save();""")
one("    w.settings = true;\n    w.open = false;",
    """    w.settings = true;
    w.open = false;
    w.notify("Customize wheel • actual-size preview");""")
one("        Some(2) => { w.open=false; w.pending=Some(3); },",
    """        Some(2) => {
            w.open=false;
            w.pending=Some(3);
            w.notify("Eraser selected");
        },""")
one("            if w.open { w.open = false; }",
    """            if w.open {
                w.open = false;
                w.notify("Wheel cancelled");
            }""")
one("                w.open=true;\n                w.hover_isolated=false;",
    """                w.open=true;
                w.hover_isolated=false;
                w.notify("Hover to highlight • tap tip to select");""")
one("                        w.pending=Some(w.slots[ix]);",
    """                        w.pending=Some(w.slots[ix]);
                        w.notify("Wheel selection accepted");""")
one("                w.open=false;\n                w.hover_isolated=false;\n                // Do not click",
    """                if w.pending.is_none() { w.notify("Wheel cancelled • tapped outside"); }
                w.open=false;
                w.hover_isolated=false;
                // Do not click""")
one("                w.open=false;\n                w.hover_isolated=false;\n            }\n            other => retained.push(other),",
    """                w.open=false;
                w.hover_isolated=false;
                w.notify("Wheel cancelled");
            }
            other => retained.push(other),""")

# PhotoCraft's user-facing customization language and layout. Keep the
# previously approved individually outlined rows and DeckCraft-brand sliders.
one('egui::Window::new("Customize Stylus Wheel")',
    'egui::Window::new("Stylus Wheel — Default")')
one('"Eight customizable shortcuts"', '"Style: Default • 8 segments"')
one('"Choose an action for each segment. An existing action swaps positions."',
    '"Choose a tool for each position. Existing selections swap positions."')
one('"The wheel preview updates live. Changes save automatically."',
    '"Actual-size preview appears beside this window. Changes save automatically."')
one('if ui.button("Reset defaults").clicked()',
    'if ui.button("Restore Default").clicked()')
one('    w.settings=show && !done;',
    """    let previously_open = w.settings;
        w.settings=show && !done;
        if previously_open && !w.settings {
            w.notify("Wheel settings saved");
        }""")

# Match PhotoCraft's alternating two-tone grey segments, 12-layer feathered
# shadow, fine separators, native white icons, and understated outer stroke.
# Crucially retain the already-approved Dk glyph draw and launcher-red hub.
start = '    let alpha=w.opacity/100.0;\n'
end = '    painter.circle_stroke(c,R*scale,Stroke::new(1.1,PINK.gamma_multiply(alpha)));\n'
if text.count(start) != 1 or text.count(end) != 1:
    raise RuntimeError("Android.5 paint anchors changed")
a = text.index(start)
b = text.index(end, a) + len(end)
paint = """    let alpha=w.opacity/100.0;
    let dark=ui.visuals().dark_mode;
    let plate=if dark { Color32::from_rgb(48,48,49) }
        else { Color32::from_rgb(244,244,245) };
    let normal_a=if dark { Color32::from_rgb(53,53,55) }
        else { Color32::from_rgb(231,232,233) };
    let normal_b=if dark { Color32::from_rgb(68,68,70) }
        else { Color32::from_rgb(209,211,213) };
    let border=if dark { Color32::from_rgb(96,96,99) }
        else { Color32::from_rgb(170,171,173) };
    let label_ink=if dark { Color32::from_rgb(214,214,216) }
        else { Color32::from_rgb(55,56,58) };
    // PhotoCraft's close, feathered 12-layer shadow, not a hard outer halo.
    for step in 0..12 {
        let spread=(12.0-step as f32*0.82)*scale;
        painter.circle_filled(c+vec2(0.8,2.0)*scale,R*scale+spread,
            Color32::from_black_alpha((2.0+step as f32*0.32) as u8));
    }
    painter.circle_filled(c,R*scale,Color32::from_rgba_unmultiplied(
        plate.r(),plate.g(),plate.b(),(245.0*alpha) as u8));
    for slot in 0..8 {
        let degrees=-90.0+slot as f32*45.0;
        let start=(degrees-21.5).to_radians();
        let end=(degrees+21.5).to_radians();
        let mut vertices=vec![c];
        for step in 0..=16 {
            let angle=start+(end-start)*step as f32/16.0;
            vertices.push(c+vec2(angle.cos(),angle.sin())*R*scale);
        }
        let selected=highlight==Some(slot);
        let base=if slot%2==0 {normal_a} else {normal_b};
        let fill=if selected {
            if dark { Color32::from_rgb(124,66,78) }
            else { Color32::from_rgb(253,196,203) }
        } else {base}.gamma_multiply(alpha);
        painter.add(Shape::convex_polygon(vertices,fill,
            Stroke::new(if selected {1.8}else{0.65},
                if selected {PINK} else {border.gamma_multiply(0.70)})));
        let theta=degrees.to_radians();
        let icon_pos=c+vec2(theta.cos(),theta.sin())*87.0*scale;
        // Use the actual DeckCraft toolbar vector paths, monochrome white.
        let icon_box=egui::Rect::from_center_size(
            icon_pos-vec2(0.0,10.0)*scale,vec2(24.0,24.0)*scale);
        if let Some(icon)=ICONS[w.slots[slot]] {
            crate::icons::paint_monochrome(&painter,icon_box,icon);
        } else {
            paint_hand_icon(&painter,icon_box,Color32::WHITE);
        }
        painter.text(icon_pos+vec2(0.0,13.0)*scale,egui::Align2::CENTER_CENTER,
            LABELS[w.slots[slot]],FontId::proportional(11.0*scale),label_ink);
    }
    painter.circle_stroke(c,R*scale,Stroke::new(0.8,border.gamma_multiply(0.58)));
"""
text = text[:a] + paint + text[b:]

# The compact 350x31 PhotoCraft message bar appears just above the bottom
# center. It never intercepts stylus/touch input or selects slides underneath.
notify_anchor = '    let pending=w.pending.take();\n'
if text.count(notify_anchor) != 1:
    raise RuntimeError("Cannot safely attach bottom-center wheel feedback")
feedback = """    // PhotoCraft-parity bottom-center notification bar: 1.9s hold, 0.5s fade.
    let elapsed=w.message_at.elapsed();
    if elapsed < FEEDBACK_HOLD + FEEDBACK_FADE {
        let alpha=if elapsed <= FEEDBACK_HOLD {1.0} else {
            1.0-(elapsed-FEEDBACK_HOLD).as_secs_f32()/FEEDBACK_FADE.as_secs_f32()
        }.clamp(0.0,1.0);
        ctx.request_repaint_after(Duration::from_millis(50));
        let screen=ctx.content_rect();
        let pill_width=(screen.width()-20.0).min(350.0).max(120.0);
        egui::Area::new(Id::new("deckcraft-wheel-bottom-notification"))
            .order(Order::Foreground)
            .fixed_pos(pos2(screen.center().x-pill_width*0.5,screen.max.y-43.0))
            .interactable(false)
            .show(ctx,|ui| {
                let (rect,_)=ui.allocate_exact_size(vec2(pill_width,31.0),Sense::hover());
                let painter=ui.painter_at(rect);
                let dark=ui.visuals().dark_mode;
                let card=if dark {Color32::from_rgb(49,49,50)}
                    else {Color32::from_rgb(247,247,248)};
                let outline=if dark {Color32::from_rgb(91,91,94)}
                    else {Color32::from_rgb(185,186,190)};
                let ink=if dark {Color32::from_rgb(232,232,234)}
                    else {Color32::from_rgb(39,40,42)};
                painter.rect_filled(rect,13.0,Color32::from_rgba_unmultiplied(
                    card.r(),card.g(),card.b(),(244.0*alpha) as u8));
                painter.rect_stroke(rect,13.0,
                    Stroke::new(1.0,outline.gamma_multiply(alpha)),
                    StrokeKind::Inside);
                painter.text(rect.center(),egui::Align2::CENTER_CENTER,w.message,
                    FontId::proportional(11.0),ink.gamma_multiply(alpha));
            });
    }
"""
text=text.replace(notify_anchor,feedback+notify_anchor,1)

# Protect the prior Android.5 logo scale (the approved final user adjustment).
for marker in (
    'vec2(30.94,19.27)*scale',
    'let image=approved_dk_logo(ui.ctx());',
    'painter.image(image.id()',
    'painter.circle_filled(c,HUB*scale,BURGUNDY);',
    'painter.circle_stroke(c,HUB*scale,Stroke::new(1.3,PINK));',
    'crate::icons::paint_monochrome',
    'paint(ctx,&w,p,None,"deckcraft-wheel-actual-size-preview")',
    'const DEFAULT_SIZE: f32 = 100.0;',
    'const DEFAULT_OPACITY: f32 = 85.0;',
    'const DEFAULT: [usize; 8] = [2, 3, 4, 1, 7, 0, 6, 5];',
    'if ui.button("Restore Default").clicked()',
    'w.size=DEFAULT_SIZE;',
    'w.opacity=DEFAULT_OPACITY;',
    'deckcraft-wheel-bottom-notification',
    'pub(crate) fn capture(ctx: &Context, raw: &mut RawInput)',
    'raw.events=retained;',
):
    if marker not in text:
        raise RuntimeError(f"Protected Wheel parity feature missing: {marker}")
if logo.stat().st_size != 128*80*4:
    raise RuntimeError("Approved launcher logo bytes changed unexpectedly")
if "PhotoCraft-style wheel" in text or "vec2(61.0,38.0)*scale" in text:
    raise RuntimeError("Removed attribution or oversized Dk lettering returned")
wheel.write_text(text,encoding="utf-8")
print("PASS: PhotoCraft wheel defaults 100%/85%; default slot layout adapted to DeckCraft tools")
print("PASS: PhotoCraft alternating grey segments, subtle feathered shadow, true-size preview")
print("PASS: PhotoCraft bottom-center fading 350x31 toast; stylus pointer isolation unchanged")
print("PASS: original Dk brand hub, user-approved small logo, native white icons, PPTX/DCS preserved")
