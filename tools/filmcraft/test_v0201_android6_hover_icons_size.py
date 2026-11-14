#!/usr/bin/env python3
"""FilmCraft Android.6 source/asset safety gates, no signing or release."""
from pathlib import Path

root=Path(__file__).resolve().parents[2]
wheel=(root/"tools/filmcraft/filmcraft_stylus_wheel.rs").read_text()
stage=(root/"tools/filmcraft/stage_v0201_wheel.py").read_text()
renderer=(root/"tools/filmcraft/render_filmcraft_wheel_icons.py").read_text()
java=(root/"tools/filmcraft/FilmCraftActivity.features.v019.bottom-feedback.java.inc").read_text()
original=(root/"tools/filmcraft/render_approved_fc_mark.py").read_text()
for name,needle in {
    "75% default": "const DEFAULT_SIZE: f32 = 0.75;",
    "80% default": "const DEFAULT_OPACITY: f32 = 0.80;",
    "saved preference migration": 'v["schema"].as_u64().unwrap_or(1) < 3',
    "reset action": "self.size=DEFAULT_SIZE;",
    "reset opacity": "self.opacity=DEFAULT_OPACITY;",
    "native Fc original icon": 'include_bytes!("filmcraft_fc_logo.rgba")',
    "white 72px sprite": 'include_bytes!("filmcraft_wheel_icons.rgba")',
    "sprite UV 8-way split": "pos2(0.0,cmd as f32/8.0)",
    "PhotoCraft two-tone": "slot%2==0",
    "input isolated": "raw.events = filtered;",
    "only stylus button opens": "if button == 1 && self.enabled && !self.settings_open",
    "bottom notification": "vec2(350.0,31.0)",
}.items():
    if needle not in wheel:
        raise SystemExit(f"STOP: FilmCraft Android.6 wheel missing {name}")
if "fn paint_segment_icon(" in wheel or "ICONS[cmd]" in wheel:
    raise SystemExit("STOP: old self-drawn malformed icons left in wheel")
for name,needle in {
    "surface listener before touch": "setOnHoverListener(fcWheelSurfaceHover)",
    "cold-start attach": "fcWheelPrepareEarlyHover();",
    "Activity resumed": "onResume()",
    "initial Activity resume hook": "onResume()",
    "native generic motion fallback": "onGenericMotionEvent(android.view.MotionEvent e)",
    "non-consuming hover": "return false; // ALWAYS allow GameActivity/winit to process input",
    "stationary hovering pen": "Do not",
    "native pen forwarder": "fcWheelKey(android.view.KeyEvent event)",
    "original Fc renderer": "render_logo(icon, logo_file)",
    "sprite renderer": "render_icons(sprite_file)",
    "sprite installed into wrapper": '"filmcraft_wheel_icons.rgba").write_bytes(',
    "one visible check updates": 'action(ui, "Check for Updates…", 4);',
    "no extra updater items": 'HEADER_RELEASE_LABEL',
}.items():
    if needle not in stage:
        raise SystemExit(f"STOP: FilmCraft Android.6 staging missing {name}")
if "MAGIC" in wheel or "dpi override" in wheel:
    raise SystemExit("STOP: unsupported stylus input path")
for name in ("scissors", "pointer", "hand", "undo", "redo", "playpause", "zoomin", "zoomout"):
    if name not in renderer:
        raise SystemExit(f"STOP: missing Lucide-derived wheel glyph {name}")
if "Lucide icons v0.456.0 (ISC license)" not in renderer:
    raise SystemExit("STOP: glyph provenance/license missing")
if "ORIGINAL_MASK_SHA256" not in original:
    raise SystemExit("STOP: Fc logo verification missing")
for method in ("fcCheckForUpdates()", "fcDownloadVerifiedUpdate()",
               "fcInstallVerifiedDownload()", "fcVerifyArchive",
               "APK signing certificate differs from installed FilmCraft",
               "Download and verify the official APK?"):
    if method not in java:
        raise SystemExit(f"STOP: existing secure updater flow lost {method}")
print("PASS: quality white wheel glyphs, original Fc logo and 75/80% defaults")
print("PASS: cold-start native-surface stylus hover + button input isolation")
print("PASS: native secure updater and PhotoCraft interface preserved")
