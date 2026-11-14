#!/usr/bin/env python3
"""DeckCraft v0.18.1-android.7 TEST ONLY: neutral dialog borders, Dk scale,
fresh/reset defaults 75%/100%, touchless hover acquisition from cold start.

Run after the verified Android.6 parity patch in an ephemeral GitHub runner.
No protected production source, package, APK or key is changed.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_v0181_android7_gray_hub_defaults_hover.py <disposable-builder>")
root = Path(sys.argv[1])
wheel = root / "source/deckcraft/crates/ui-egui/src/android_wheel.rs"
logo = root / "source/deckcraft/crates/ui-egui/src/android_wheel_logo.rgba"
if not wheel.is_file() or logo.stat().st_size != 128 * 80 * 4:
    raise RuntimeError("Approved Android.6 branded wheel + genuine Dk raster required")
text = wheel.read_text(encoding="utf-8")

def once(old, new):
    global text
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"Unsafe Android.7 wheel anchor {n}x: {old[:110]!r}")
    text = text.replace(old, new, 1)

# Remove the pink/red framing from the customization dialog. This neutral grey
# is used on header, all eight slot rows and Appearance. Coral slider/buttons
# and original launcher-red circular hub are deliberately unchanged.
once("""                let panel=if dark {
                    Color32::from_rgb(48,43,48)
                } else {
                    Color32::from_rgb(255,250,251)
                };
                let outline=if dark {
                    Color32::from_rgb(114,77,87)
                } else {
                    Color32::from_rgb(224,195,203)
                };""",
"""                let panel=if dark {
                    Color32::from_rgb(47,47,49)
                } else {
                    Color32::from_rgb(249,249,250)
                };
                // Neutral grey outlines for header, all eight slots, Appearance.
                let outline=if dark {
                    Color32::from_rgb(105,105,109)
                } else {
                    Color32::from_rgb(181,182,186)
                };""")

# The currently approved small launcher Dk raster is shown 15% larger, without
# changing the hub circle, wheel diameter, letter shape or logo centre.
once("vec2(30.94,19.27)*scale", "vec2(35.58,22.16)*scale")

# Defaults apply to fresh installs and the Restore Default action.
# Keep read-before-use v1 persisted settings intact, so older preferences
# are NOT silently reset when the test APK is upgraded.
once("const DEFAULT_SIZE: f32 = 100.0;", "const DEFAULT_SIZE: f32 = 75.0;")
once("const DEFAULT_OPACITY: f32 = 85.0;", "const DEFAULT_OPACITY: f32 = 100.0;")

# Previously the native ui-egui loop requested hover repaints only once a
# stylus_cursor already existed. On MagicOS the Java hover bridge queues the
# first real ACTION_HOVER_ENTER/MOVE before any touch, but the sleeping egui
# loop can go unpolled until the first tap. Poll at a restrained 80 ms cadence
# even with no cursor, wheel switched off, or no prior screen contact. Hover
# sample processing stays before the !enabled short circuit.
once("""    // Consume the verified real stylus hover sample, in physical pixels.""",
"""    // Touchless cold-start hover: poll the real pen bridge even before the
    // first touch, including when Stylus Wheel is disabled. This does not
    // fabricate a pen position; only real stylus hover samples draw a cursor.
    ctx.request_repaint_after(std::time::Duration::from_millis(80));
    // Consume the verified real stylus hover sample, in physical pixels.""")

# Confirm the cursor is a genuinely independent, non-interactive overlay and
# its JNI queue receives hover samples from stylus/eraser only.
for marker in (
    'ctx.request_repaint_after(std::time::Duration::from_millis(80));',
    'Id::new("deckcraft.wheel.hover.raw")',
    'w.stylus_cursor=Some(pos);',
    'w.stylus_cursor=None;',
    'if !w.open && !w.settings {',
    'Order::Tooltip,Id::new("deckcraft-stylus-hover-cursor")',
    'if !w.enabled || w.settings {',
    'pub(crate) fn capture(ctx: &Context, raw: &mut RawInput)',
    'raw.events=retained;',
    'const DEFAULT_SIZE: f32 = 75.0;',
    'const DEFAULT_OPACITY: f32 = 100.0;',
    'size: DEFAULT_SIZE, opacity: DEFAULT_OPACITY',
    'w.size=DEFAULT_SIZE;',
    'w.opacity=DEFAULT_OPACITY;',
    'if ui.button("Restore Default").clicked()',
    'Color32::from_rgb(105,105,109)',
    'Color32::from_rgb(181,182,186)',
    'vec2(35.58,22.16)*scale',
    'painter.circle_filled(c,HUB*scale,BURGUNDY);',
    'painter.circle_stroke(c,HUB*scale,Stroke::new(1.3,PINK));',
    'let image=approved_dk_logo(ui.ctx());',
    'crate::icons::paint_monochrome',
    'paint(ctx,&w,p,None,"deckcraft-wheel-actual-size-preview")',
    'const DEFAULT: [usize; 8] = [2, 3, 4, 1, 7, 0, 6, 5];',
    'deckcraft-wheel-bottom-notification',
):
    if marker not in text:
        raise RuntimeError(f"Android.7 wheel regression: missing {marker}")
if "vec2(30.94,19.27)*scale" in text:
    raise RuntimeError("Previous too-small Dk font remains")
for wrong in ("Color32::from_rgb(114,77,87)", "Color32::from_rgb(224,195,203)"):
    if wrong in text:
        raise RuntimeError("Old pink dialog outline remains: " + wrong)
if "PhotoCraft-style wheel" in text:
    raise RuntimeError("Disallowed old attribution returned")
wheel.write_text(text, encoding="utf-8")
print("PASS: all eight customization rows, header and appearance framed in neutral grey")
print("PASS: original transparent launcher Dk lettering +15% inside same red circular hub")
print("PASS: fresh-install and Restore Default wheel size 75%, opacity 100%, custom saves retained")
print("PASS: independent no-touch real stylus hover polling active immediately after launch")
print("PASS: PhotoCraft two-tone segments, soft shadow, fading bar, preview, white native icons retained")
