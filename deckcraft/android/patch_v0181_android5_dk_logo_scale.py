#!/usr/bin/env python3
"""DeckCraft Android.5 TEST ONLY — scale the original launcher Dk glyph.

Runs after Android.4 customization polish in the disposable ARM64 builder.
Visual proposals were 30% smaller, 30% smaller again, 15% larger, and
then 10% smaller: 0.70 * 0.70 * 1.15 * 0.90 = 0.50715 baseline scale.
Only the centered transparent Dk logo draw rect changes, not the red hub,
tool icons, position, hover capture, sliders, preview or preferences.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_v0181_android5_dk_logo_scale.py <disposable-builder>")
root = Path(sys.argv[1])
wheel = root / "source/deckcraft/crates/ui-egui/src/android_wheel.rs"
logo = root / "source/deckcraft/crates/ui-egui/src/android_wheel_logo.rgba"
if not wheel.is_file() or not logo.is_file():
    raise RuntimeError("Android.4 branded wheel must be staged before Dk scale patch")
text = wheel.read_text(encoding="utf-8")
old = """        egui::Rect::from_center_size(c-vec2(0.0,8.0)*scale,
            vec2(61.0,38.0)*scale),"""
new = """        egui::Rect::from_center_size(c-vec2(0.0,8.0)*scale,
            vec2(30.94,19.27)*scale),"""
if text.count(old) != 1:
    raise RuntimeError(f"DeckCraft.5 unsafe Dk image bounds anchor: {text.count(old)} matches")
text = text.replace(old, new, 1)
for required in (
    "let image=approved_dk_logo(ui.ctx());",
    "painter.image(image.id()",
    "painter.circle_filled(c,HUB*scale,BURGUNDY);",
    "painter.circle_stroke(c,HUB*scale,Stroke::new(1.3,PINK));",
    'highlight.map(|i| LABELS[w.slots[i]]).unwrap_or("Default")',
    "crate::icons::paint_monochrome",
    "pub(crate) fn capture(ctx: &Context, raw: &mut RawInput)",
    'paint(ctx,&w,p,None,"deckcraft-wheel-actual-size-preview")',
    "const DEFAULT_SIZE: f32 = 75.0;",
    "const DEFAULT_OPACITY: f32 = 85.0;",
):
    if required not in text:
        raise RuntimeError(f"DeckCraft.5 protected wheel feature missing: {required}")
if logo.stat().st_size != 128*80*4:
    raise RuntimeError("Approved launcher Dk raster changed unexpectedly")
wheel.write_text(text, encoding="utf-8")
print("PASS: original launcher Dk glyph scaled to 50.715% (last proposal reduced 10%)")
print("PASS: exact launcher hub, white icons, 8 bordered slots, hover, live preview, defaults retained")
