#!/usr/bin/env python3
"""DeckCraft 0.18.1-android.3 TEST ONLY: round launcher-colour hub, glyph-only Dk, coral sliders.

Runs AFTER Android.1 and Android.2 overlays in a disposable builder checkout.
Fail-closed anchor checks; does not edit upstream, production releases or signing keys.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from statistics import median
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: patch_v0181_android3_brand_hub_slider.py <builder> <approved DeckCraft.png>")
root=Path(sys.argv[1])
source=Path(sys.argv[2])
ui=root/"source/deckcraft/crates/ui-egui/src"
wheel=ui/"android_wheel.rs"
logo=ui/"android_wheel_logo.rgba"
if not wheel.is_file() or not logo.is_file():
    raise RuntimeError("Android.2 wheel and approved Dk raster must already exist")
def one(old,new):
    content=wheel.read_text(encoding="utf-8")
    matches=content.count(old)
    if matches != 1:
        raise RuntimeError(f"DeckCraft.3 integration anchor changed ({matches}): {old[:100]!r}")
    wheel.write_text(content.replace(old,new,1),encoding="utf-8")

# Extract the coral Dk strokes directly from the approved DeckCraft launcher.
# Unlike Android.2's red-channel selection, the GREEN channel cleanly separates
# pink ink (G ~ 110) from the deep red launcher tile (G ~ 0). This removes
# the entire rectangular tile instead of making a flat coloured rectangle.
image=Image.open(source).convert("RGBA")
width,height=image.size
if width < 256 or height < 256:
    raise RuntimeError("Approved DeckCraft source is not a full-resolution launcher icon")
background=image.getpixel((width//2,height//12))
# Measure actual brand pink from the owner's supplied icon, not a guessed palette.
pink_samples=[]
for y in range(height//5, height*4//5, max(1,height//96)):
    for x in range(width//10, width*9//10, max(1,width//96)):
        r,g,b,a=image.getpixel((x,y))
        if a>220 and g>65 and b>55 and r>185 and r>g*1.7:
            pink_samples.append((r,g,b))
if len(pink_samples)<100:
    raise RuntimeError("Could not reliably isolate the approved Dk pink ink")
pink=tuple(int(median(c[i] for c in pink_samples)) for i in range(3))
if not (pink[0]>210 and pink[1]>background[1]+40 and pink[2]>background[2]+35):
    raise RuntimeError(f"Expected coral ink on red Dk tile, got ink {pink}, tile {background}")
if background[3]<240:
    raise RuntimeError("Approved launcher background was transparent at centre-top")
# This is a normalized coverage mask, not brightness-based red selection.
# The bounding box is derived from the ink only and is verified to be smaller
# than the rounded-square launcher tile.
green=image.getchannel("G")
bg_g=background[1]
fg_g=pink[1]
coverage=green.point(lambda v: max(0,min(255,round(255*(v-bg_g)/(fg_g-bg_g)))))
# Prevent transparent PNG corners and edges from leaking white into the glyph.
coverage=ImageChops.multiply(coverage,image.getchannel("A"))
bounds=coverage.point(lambda x: 255 if x>28 else 0).getbbox()
if bounds is None:
    raise RuntimeError("No Dk glyph pixels isolated")
x0,y0,x1,y1=bounds
if x0 < width*.03 or x1 > width*.97 or y0 < height*.08 or y1>height*.92:
    raise RuntimeError(f"Logo extraction likely includes square tile, bounds={bounds}, icon={image.size}")
if (x1-x0) < width*.40 or (y1-y0)<height*.25:
    raise RuntimeError(f"Dk glyph unexpectedly small or incomplete: {bounds}")
# Preserve antialiasing but use a single uniform sampled foreground colour.
fg=Image.new("RGBA",image.size,(*pink,0))
fg.putalpha(coverage)
fg=fg.crop(bounds)
# Constrain to actual hub lettering without stretching original proportions.
fg.thumbnail((118,68),Image.Resampling.LANCZOS)
out=Image.new("RGBA",(128,80),(0,0,0,0))
out.alpha_composite(fg,((128-fg.width)//2,(80-fg.height)//2))
# Proof: transparent edges; no square, no solid rectangular tile.
a=out.getchannel("A")
if any(a.getpixel(xy)>8 for xy in [(0,0),(127,0),(0,79),(127,79),(64,0),(0,40),(127,40)]):
    raise RuntimeError("Dk glyph-only raster contains an opaque rectangular edge")
if (a.getbbox() is None) or a.getextrema()[1]<220:
    raise RuntimeError("Dk launcher glyph raster missing opaque pink strokes")
logo.write_bytes(out.tobytes())
assert logo.stat().st_size==128*80*4

# Round hub background uses the EXACT sampled colour of the owner's launcher
# (no imposed square/rect, no unrelated burgundy approximation).
old='const BURGUNDY: Color32 = Color32::from_rgb(61, 5, 28);'
brand=f'const BURGUNDY: Color32 = Color32::from_rgb({background[0]}, {background[1]}, {background[2]});'
one(old,brand)
# Use the exact pink sampled from the launcher for the ring and sliders too.
one('const PINK: Color32 = Color32::from_rgb(239, 69, 105);',
    f'const PINK: Color32 = Color32::from_rgb({pink[0]}, {pink[1]}, {pink[2]});')

# Replace the native themed sliders with a scoped, genuine coral pink
# paint/drag widget. This affects only DeckCraft's wheel customization,
# never the editor's other controls or cursor/scroll behaviour.
one('''                changed|=ui.add(egui::Slider::new(&mut w.size,75.0..=125.0)
                    .text("Wheel size").suffix("%")).changed();
                changed|=ui.add(egui::Slider::new(&mut w.opacity,60.0..=100.0)
                    .text("Opacity").suffix("%")).changed();''',
'''                changed |= deckcraft_slider(ui, "Wheel size", &mut w.size, 75.0, 125.0);
                changed |= deckcraft_slider(ui, "Opacity", &mut w.opacity, 60.0, 100.0);''')
one('''fn paint(ctx:&Context,w:&Wheel,center:Pos2,highlight:Option<usize>,id:&'static str) {''',
'''/// Wheel-only branded slider.  Coral fill + coral thumb on a subtle
/// launcher-red rail in both dark and light themes. Uses normal egui pointer
/// input, so touch, stylus and trackpad click/drag work without custom hooks.
fn deckcraft_slider(ui:&mut Ui,label:&str,value:&mut f32,min:f32,max:f32)->bool {
    ui.horizontal(|ui| {
        ui.set_min_height(31.0);
        ui.add_sized([88.0,24.0],egui::Label::new(label));
        let (rect,response)=ui.allocate_exact_size(vec2(174.0,26.0),
            Sense::click_and_drag());
        let left=rect.left()+9.0;
        let right=rect.right()-9.0;
        let track=egui::Rect::from_min_max(pos2(left,rect.center().y-3.4),
            pos2(right,rect.center().y+3.4));
        let mut changed=false;
        if response.clicked() || response.dragged() {
            if let Some(p)=response.interact_pointer_pos() {
                let proportion=((p.x-left)/(right-left)).clamp(0.0,1.0);
                let proposed=(min+(max-min)*proportion).round();
                if (*value-proposed).abs()>0.001 {
                    *value=proposed;
                    changed=true;
                }
            }
        }
        let t=((*value-min)/(max-min)).clamp(0.0,1.0);
        let knob_x=left+(right-left)*t;
        let painter=ui.painter();
        painter.rect_filled(track,3.4,Color32::from_rgb(107,59,72));
        if knob_x>left {
            let fill=egui::Rect::from_min_max(track.min,
                pos2(knob_x,track.max.y));
            painter.rect_filled(fill,3.4,PINK);
        }
        painter.circle_filled(pos2(knob_x,rect.center().y),8.3,PINK);
        painter.circle_stroke(pos2(knob_x,rect.center().y),8.3,
            Stroke::new(1.4,Color32::WHITE));
        ui.add_sized([51.0,24.0],egui::Label::new(format!("{:.0}%",*value)));
        changed
    }).inner
}
fn paint(ctx:&Context,w:&Wheel,center:Pos2,highlight:Option<usize>,id:&'static str) {''')

# Ensure only circular hub + transparent glyph image, never a square.
final=wheel.read_text(encoding="utf-8")
assert 'painter.circle_filled(c,HUB*scale,BURGUNDY);' in final
assert 'let image=approved_dk_logo(ui.ctx());' in final
assert 'painter.image(image.id()' in final
assert 'painter.rect_filled(c,HUB' not in final
assert 'deckcraft_slider(ui, "Wheel size"' in final
assert 'deckcraft_slider(ui, "Opacity"' in final
assert 'crate::icons::paint_monochrome(&painter' in final
assert 'dkWheelTakeHover' in (root/"templates/android/SafActivity.java").read_text()
print(f"PASS: exact launcher-round hub RGB {background[:3]}, sampled pink RGB {pink}")
print(f"PASS: Dk glyph-only transparent raster {bounds} => {fg.size}; no square backing")
print("PASS: scoped coral-pink size/opacity sliders, real stylus hovering and white icons preserved")
