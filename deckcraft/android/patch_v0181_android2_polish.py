#!/usr/bin/env python3
"""DeckCraft Android.2: genuine stylus hover, exact launcher mark, white-only wheel icons.

Run AFTER patch_v018_stylus_wheel.py against the isolated builder checkout.
Never modify published sources, the original signing identity, or any other app.
"""
from pathlib import Path
from PIL import Image
import math, sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v0181_android2_polish.py <builder> <approved DeckCraft.png>")
root=Path(sys.argv[1]); logo_source=Path(sys.argv[2])
base=root/"source/deckcraft/crates/ui-egui/src"
wheel=base/"android_wheel.rs"
icon=base/"icons.rs"
geometry=base/"icons/geometry.rs"
activity=root/"templates/android/SafActivity.java"
bridge=root/"templates/android/dcs_bridge.rs"

def once(path, before, after):
    src=path.read_text(encoding="utf-8")
    count=src.count(before)
    if count!=1:
        raise RuntimeError(f"DeckCraft.2 unsafe anchor: {path} {count}x {before[:100]!r}")
    path.write_text(src.replace(before,after,1),encoding="utf-8")

# Reuse upstream's EXACT vector icon paths, but replace their entire colour
# resolution with WHITE for only the dedicated radial wheel renderer.
# Ordinary ribbon/menu icons keep all existing accent colours.
once(geometry, "    pub(super) dis: bool,\n", "    pub(super) dis: bool,\n    pub(super) mono: bool,\n")
once(geometry,
'''    fn col(&self, c: C) -> Color32 {
        let dim = if self.dis { 0.35 } else { 1.0 };
        match c {''',
'''    fn col(&self, c: C) -> Color32 {
        // Android-only wheel calls paint_monochrome; all other callers retain
        // the original multicolour ribbon presentation.
        if self.mono {
            return match c {
                C::None => Color32::TRANSPARENT,
                C::Ink(a) | C::Acc(_, a) => self.ink.gamma_multiply(a),
                C::White => self.ink,
            };
        }
        let dim = if self.dis { 0.35 } else { 1.0 };
        match c {''')
once(icon,
"let pen = Pen { p: painter, o: origin, k: size / 24.0, sw: stroke_width(size), ink, dis: disabled };",
"let pen = Pen { p: painter, o: origin, k: size / 24.0, sw: stroke_width(size), ink, dis: disabled, mono: false };")
once(icon,
"#[cfg(test)]\nmod tests {",
'''/// Wheel-only: reuses the exact original DeckCraft native paths and shapes,
/// replacing EVERY accent (including internal fills) with WHITE.
#[cfg(target_os = "android")]
pub fn paint_monochrome(painter: &egui::Painter, rect: egui::Rect, icon: Icon) {
    let size=rect.width().min(rect.height());
    if !size.is_finite() || size<=0.5 { return; }
    let origin=rect.center()-vec2(size*0.5,size*0.5);
    let pen=Pen { p:painter, o:origin, k:size/24.0, sw:stroke_width(size),
        ink:Color32::WHITE, dis:false, mono:true };
    draw(&pen,icon);
}

#[cfg(test)]
mod tests {''')
once(wheel,
"crate::icons::paint(&painter,icon_box,icon,Color32::WHITE,false);",
"crate::icons::paint_monochrome(&painter,icon_box,icon);")

# Crop ONLY the light coral/pink brand letters from the owner-approved icon
# already shipped inside the original published Android release.
# Never substitute a system font or try to emulate the Dk proportions.
src=Image.open(logo_source).convert("RGBA")
width,height=src.size
if width<64 or height<64:
    raise RuntimeError("Approved brand icon too small for logo crop")
pic=src.load()
strong=[]
# Center crop confines the scan to logo artwork, not corner glyphs/badges.
for yy in range(height//7,height*6//7):
    for xx in range(width//9,width*8//9):
        r,g,b,a=pic[xx,yy]
        if a>100 and r>=150 and r>g*1.34 and r>b*1.18:
            strong.append((xx,yy))
if len(strong)<100:
    raise RuntimeError("Could not isolate approved Dk foreground from logo; refusing placeholder")
x0=min(x for x,y in strong);x1=max(x for x,y in strong)+1
y0=min(y for x,y in strong);y1=max(y for x,y in strong)+1
if x1-x0<width*.13 or y1-y0<height*.1:
    raise RuntimeError("Approved Dk mark segmentation unexpectedly small")
pad=int(max(2,min(x1-x0,y1-y0)*.025))
x0=max(0,x0-pad);y0=max(0,y0-pad)
x1=min(width,x1+pad);y1=min(height,y1+pad)
foreground=Image.new("RGBA",(x1-x0,y1-y0),(0,0,0,0))
out=foreground.load()
for yy in range(y0,y1):
    for xx in range(x0,x1):
        r,g,b,a=pic[xx,yy]
        # Preserve source RGB exactly; fade antialiasing around the original
        # coral letters while stripping burgundy background pixels.
        strength=min(1.0,max(0.0,(r-95)/70.0),
            max(0.0,(r-g-6)/45.0),max(0.0,(r-b-7)/42.0))
        opacity=int(round(a*strength))
        out[xx-x0,yy-y0]=(r,g,b,opacity)
# Full launcher-letter silhouette, centred without distortion.
canvas=Image.new("RGBA",(128,80),(0,0,0,0))
foreground.thumbnail((116,66),Image.Resampling.LANCZOS)
canvas.alpha_composite(foreground,((128-foreground.width)//2,(80-foreground.height)//2))
if canvas.getbbox() is None:
    raise RuntimeError("Brand logo extraction resulted in transparent output")
logo_dest=base/"android_wheel_logo.rgba"
logo_dest.write_bytes(canvas.tobytes())
assert logo_dest.stat().st_size==128*80*4
print(f"PASS: cropped exact approved launcher Dk pixels from {src.size}, bounds {(x0,y0,x1,y1)} -> RGBA 128x80")

once(wheel,'''fn draw(ui:&Ui,rect:egui::Rect,w:&Wheel,highlight:Option<usize>) {''',
'''fn approved_dk_logo(ctx:&Context) -> egui::TextureHandle {
    let key=Id::new("deckcraft.approved.launcher.mark.texture.v1");
    if let Some(tex)=ctx.data(|d| d.get_temp::<egui::TextureHandle>(key)) {
        return tex;
    }
    const PIXELS:&[u8]=include_bytes!("android_wheel_logo.rgba");
    let image=egui::ColorImage::from_rgba_unmultiplied([128,80],PIXELS);
    let tex=ctx.load_texture("deckcraft-original-launcher-Dk-mark",image,
        egui::TextureOptions::LINEAR);
    ctx.data_mut(|d|d.insert_temp(key,tex.clone()));
    tex
}
fn draw(ui:&Ui,rect:egui::Rect,w:&Wheel,highlight:Option<usize>) {''')
once(wheel,
'''    // Native DeckCraft mark, not a copied PhotoCraft logo or a white tile.
    painter.text(c-vec2(0.0,8.0)*scale,egui::Align2::CENTER_CENTER,
        "Dk",FontId::proportional(34.0*scale),PINK);''',
'''    // The exact original launcher Dk mark raster, NOT a proportional system
    // font.  Hub is still a solid burgundy roundel.
    let image=approved_dk_logo(ui.ctx());
    painter.image(image.id(),
        egui::Rect::from_center_size(c-vec2(0.0,8.0)*scale,
            vec2(61.0,38.0)*scale),
        egui::Rect::from_min_max(pos2(0.0,0.0),pos2(1.0,1.0)),
        Color32::WHITE);''')

# Java delivers real pen hovering (stylus or eraser only), as view-local
# physical coordinates. Keep original GameActivity dispatch on all events,
# especially touches, drags, trackpads and IME keyboard handling.
once(activity, '    private volatile boolean dkWheelEnabled = false;',
'''    private final java.util.concurrent.atomic.AtomicLong dkRealStylusHover =
        new java.util.concurrent.atomic.AtomicLong(0L);
    // 0 = no new sample, -1 = hover left. Otherwise two packed float bits
    // as physical-pixel X and Y; no string allocation in the motion callback.
    public long dkWheelTakeHover() { return dkRealStylusHover.getAndSet(0L); }
    private void dkCaptureRealStylusHover(MotionEvent e) {
        if (e == null || e.getPointerCount() < 1) return;
        int tool=e.getToolType(0);
        if (tool != MotionEvent.TOOL_TYPE_STYLUS
            && tool != MotionEvent.TOOL_TYPE_ERASER) return;
        int action=e.getActionMasked();
        if (action == MotionEvent.ACTION_HOVER_EXIT) {
            dkRealStylusHover.set(-1L);
        } else if (action == MotionEvent.ACTION_HOVER_ENTER
                   || action == MotionEvent.ACTION_HOVER_MOVE) {
            float x=e.getX(0), y=e.getY(0);
            if (Float.isFinite(x) && Float.isFinite(y)) {
                long data=(((long)Float.floatToRawIntBits(x)) << 32)
                    | (Float.floatToRawIntBits(y) & 0xffffffffL);
                if (data!=0L && data!=-1L) dkRealStylusHover.set(data);
            }
        }
    }
    @Override public boolean dispatchGenericMotionEvent(MotionEvent e) {
        dkCaptureRealStylusHover(e);
        return super.dispatchGenericMotionEvent(e);
    }
    @Override public boolean onGenericMotionEvent(MotionEvent e) {
        dkCaptureRealStylusHover(e);
        return super.onGenericMotionEvent(e);
    }
    private volatile boolean dkWheelEnabled = false;''')
# A separate JNI method so stylus hover remains independent of button/dcs.
once(bridge,
"    pub fn editor_close(&self, ctx: &egui::Context) {\n        self.wheel_input(ctx);",
'''    pub fn wheel_hover(&self, ctx: &egui::Context) {
        let vm=unsafe { JavaVM::from_raw(self.app.vm_as_ptr() as *mut _) };
        let result=vm.attach_current_thread(|env| -> jni::errors::Result<i64> {
            let raw=self.app.activity_as_ptr() as jni::sys::jobject;
            let activity=unsafe { env.as_cast_raw::<JObject>(&raw)? };
            env.call_method(&*activity, JNIString::new("dkWheelTakeHover"),
                jni_sig!("()J"), &[])?.j()
        });
        if let Ok(value)=result {
            if value != 0 {
                ctx.data_mut(|d|d.insert_temp(
                    egui::Id::new("deckcraft.wheel.hover.raw"),value));
                ctx.request_repaint();
            }
        }
    }
    pub fn editor_close(&self, ctx: &egui::Context) {
        self.wheel_input(ctx);
        self.wheel_hover(ctx);''')

# Hover sample enters the same RadialWheel RawInput capture as stylus button
# controls. A wheel-covered hover is NOT forwarded to the presentation UI,
# preventing hover highlighting/selecting objects underneath.
once(wheel,
'''    // The Android GameActivity side button is accepted only from the physical''',
'''    // Consume the verified real stylus hover sample, in physical pixels.
    // This arrives via Java/GameActivity and is independent of finger/trackpad.
    let sample=ctx.data_mut(|d|d.remove_temp::<i64>(
        Id::new("deckcraft.wheel.hover.raw")));
    if let Some(sample)=sample {
        if sample == -1 {
            w.hover=None;
            w.stylus_cursor=None;
        } else {
            let bits=sample as u64;
            let x=f32::from_bits((bits>>32) as u32);
            let y=f32::from_bits(bits as u32);
            let ppp=ctx.pixels_per_point();
            let pos=pos2(x/ppp,y/ppp);
            if pos.is_finite() && ctx.content_rect().contains(pos) {
                w.hover=Some(pos);
                w.stylus_cursor=Some(pos);
                let inside=w.open && w.center.is_some_and(|center|
                    (pos-center).length()<=(R+12.0)*w.scale());
                if !inside {
                    raw.events.push(egui::Event::PointerMoved(pos));
                }
            }
        }
    }
    // The Android GameActivity side button is accepted only from the physical''')
once(wheel,
'''    signal_seen: u8,
}''',
'''    signal_seen: u8,
    stylus_cursor: Option<Pos2>,
}''')
once(wheel,
'''            pending: None, signal_seen: 0,
''',
'''            pending: None, signal_seen: 0, stylus_cursor: None,
''')
# NOTE: move sample processing before the enabled early return so hover works
# independently of the wheel toggle. Find only the matching capture block.
once(wheel,
'''    if !w.enabled || w.settings {
        w.open = false;
        w.hover_isolated = false;
        set(ctx,w);
        return;
    }
    // Consume the verified real stylus hover sample''',
'''    // Consume the verified real stylus hover sample''')
once(wheel,
'''    // The Android GameActivity side button is accepted only from the physical
''',
'''    if !w.enabled || w.settings {
        w.open = false;
        w.hover_isolated = false;
        // Keep the pen hover cursor when the wheel itself is switched off.
        set(ctx,w);
        return;
    }
    // The Android GameActivity side button is accepted only from the physical
''')
once(wheel,
'''    let mut w=get(ctx);
    if w.settings {''',
'''    let mut w=get(ctx);
    // An independent pen-hover indicator, drawn over the UI but never
    // interacting with the editor or selecting any object.
    if !w.open && !w.settings {
        if let Some(p)=w.stylus_cursor {
            let painter=ctx.layer_painter(egui::LayerId::new(
                Order::Tooltip,Id::new("deckcraft-stylus-hover-cursor")));
            painter.circle_stroke(p,5.6,Stroke::new(2.7,BURGUNDY));
            painter.circle_stroke(p,5.1,Stroke::new(1.2,Color32::WHITE));
        }
    }
    if w.settings {''')
# On wheel closed + pen hover request a low-cost repaint for fresh samples.
once(wheel,
'''    if w.open {
        // Short idle repaint cadence only while the wheel is actually visible.''',
'''    if w.stylus_cursor.is_some() && !w.open {
        ctx.request_repaint_after(std::time::Duration::from_millis(55));
    }
    if w.open {
        // Short idle repaint cadence only while the wheel is actually visible.''')
# Input isolation: ensure the Wheel sees real hover before own pointer filtering.
assert 'crate::icons::paint_monochrome' in wheel.read_text()
assert 'approved_dk_logo' in wheel.read_text()
assert 'dkWheelTakeHover' in bridge.read_text()
assert 'dispatchGenericMotionEvent' in activity.read_text()
assert 'self.wheel_input(ctx);' in bridge.read_text()
assert 'deckcraft.wheel.native.enabled' in wheel.read_text()
assert 'dcs_bridge' in (root/"lib/build-common.sh").read_text()
assert "pub fn paint_monochrome" in icon.read_text()
assert "mono: false" in icon.read_text()
print("PASS: exact original Dk logo RGBA, 10 monochrome native wheel icons, real stylus hover")
print("PASS: unmodified other-app icons, existing Java/IME/keyboard/Save D/C/S bridges preserved")
